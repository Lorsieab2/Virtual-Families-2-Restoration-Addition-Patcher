// vf2outfits_b200.dll -- "Outfit Pictures", the companion DLL for the B200 Virtual Families 2 executable.
// One fix, one DLL: nothing else is installed here. Part of the Fix Vanilla Game Bugs setting.
//
// The stock bug (every step proved by a pin of runtime/b200_outfits_sites.py): the store shows three
// pictures per sex. Buying one (CScrollingStoreScene::HandlePurchaseItem) copies that picture into ONE
// field per sex (CInventoryManager +468h male, +46Ch female) and puts a Male Outfit (49h) or Female Outfit
// (4Ah) into the tool tray. The tray keeps only (item, uses) per place. The tray draws every outfit of a sex
// with that one field (CToolTray::Draw and DrawToolInHand through DrawItem), and putting one on gives the
// villager that one field (theMainScene::HandleMouseDown's GetOutfit(49h / 4Ah)). So every outfit of a sex
// in the tray shows, and puts on, the last one bought.
//
// The fix: each tray place keeps its own picture, here, in memory:
//   the buy's AddItem call             the place AddItem fills gets the picture just bought;
//   the tray's two SwapSlots calls     the pictures move with the outfits (a click and a drop);
//   the tray's two DrawItem calls      the place's own picture is lent to +468h / +46Ch for that one call,
//                                      and the field is put back at once (the saved field never changes);
//   the apply's two GetOutfit calls    the place in the hand gives its own picture.
// A place whose picture is not known (an outfit bought before the fix, a save the sidecar does not
// describe, or anything the DLL cannot vouch for) gives exactly what the stock game gives. The patcher's
// own expansion outfits and hairstyles are other tray items: they never reach this DLL's pictures and
// their GetOutfit answer is the executable's own, as before.
//
// The pictures of a save are kept beside it in a sidecar ("<save folder>\Virtual Families 2 Patcher
// Data\Outfits\<save file>.dat"), never in a game record and never in the save. It is versioned and
// checksummed, written after theGameState::Save (a temp file, then a replace), and used after a load only
// when it describes the save just loaded: the save file's hash and the tray and outfit fields the save
// holds. The game's own backup of the previous save (slot + 20) gets the previous sidecar the same way. A
// damaged sidecar is moved aside, a sidecar another program holds is never replaced or moved, and a save
// with no sidecar (an old save) shows the stock pictures.
//
// The B200 executable is RELOCATED (DYNAMICBASE) and each of the 32 matrix variants links to different
// addresses, so this DLL holds NO game address. b200outfits_sites.h (generated and proved by
// runtime/tools/gen_b200_outfits_sites.py) holds whole stock functions and runs of the core variant with
// wildcards where a relocated field or a call displacement sits; Resolve() finds every one in the live
// image exactly once and derives each address from where they were found.
//
// The executable's loader (theGame::Init's first call) loads this DLL once, after the other companion DLLs,
// only while the Fix Vanilla Game Bugs byte (.vf2bugs) is 1, and calls B200Outfits_Startup(). Installing
// is: setting -> resolve -> plan -> apply, all or nothing. With the setting off, or anything the resolver
// cannot prove, NOTHING is written and the game is B200's own bytes.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include "b200outfits_sites.h"

// ---------------------------------------------------------------- the sites
static unsigned Sites[OUTF_SITE_COUNT];
#define SITE(name) (Sites[OUTF_SITE_##name])

// ---------------------------------------------------------------- status block
// B200Outfits_Status: what this launch installed, and what the last load and save did.
//   magic 'B2OP', version, requested, resolved, installed, writeMask, known (tray places whose picture is
//   known), lastLoad (0 none, 1 the sidecar of this save, 2 the backup's sidecar, 3 the sidecar of another
//   copy of this save whose tray and outfits match, 4 nothing to use, 5 a damaged sidecar moved aside,
//   6 sidecar shut (in use: left as it is), 7 a damaged sidecar that could not be moved aside (left as it
//   is)), lastSave (0 none, 1 written, 2 nothing to write, 3 write failed, 4 a sidecar was shut or could
//   not be moved aside: nothing was written or replaced), applied (outfits put on with a kept picture),
//   lent (draws that showed a kept picture)
struct OutfitsStatus {
    unsigned magic;
    unsigned version;
    unsigned requested;
    unsigned resolved;
    unsigned installed;
    unsigned writeMask;
    unsigned known;
    unsigned lastLoad;
    unsigned lastSave;
    unsigned applied;
    unsigned lent;
};
extern "C" __declspec(dllexport) volatile OutfitsStatus B200Outfits_Status = {
    OUTF_STATUS_MAGIC, 1u, 0, 0, 0, 0, 0, 0, 0, 0, 0 };

static HMODULE ThisModule;
static wchar_t Folder[MAX_PATH];

static void Copy(void *dst, const void *src, unsigned n) {
    volatile unsigned char *d = (volatile unsigned char *)dst;
    const volatile unsigned char *s = (const volatile unsigned char *)src;
    for (unsigned i = 0; i < n; ++i) d[i] = s[i];
}

static void Zero(void *dst, unsigned n) {
    volatile unsigned char *d = (volatile unsigned char *)dst;
    for (unsigned i = 0; i < n; ++i) d[i] = 0;
}

// ---------------------------------------------------------------- log
// vf2outfits.log beside the DLL: what this launch installed, and one line per load and save that used or
// wrote a sidecar. Not in the emulator test build.
static bool LogStarted;

#ifdef B200OUTFITS_TEST
static void Log(const char *, unsigned = 0, unsigned = 0, const char * = 0) {}
#else
static unsigned Append(char *out, unsigned n, unsigned cap, const char *s) {
    while (s && *s && n + 1 < cap) out[n++] = *s++;
    return n;
}

static unsigned AppendNumber(char *out, unsigned n, unsigned cap, unsigned v) {
    char digits[12];
    unsigned k = 0;
    do { digits[k++] = (char)('0' + v % 10); v /= 10; } while (v && k < 11);
    while (k && n + 1 < cap) out[n++] = digits[--k];
    return n;
}

// fmt: %u = a, then b; %s = text.
static void Log(const char *fmt, unsigned a = 0, unsigned b = 0, const char *text = 0) {
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    while (Folder[n] && n + 16 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *name = L"vf2outfits.log";
    for (unsigned i = 0; name[i]; ++i) path[n++] = name[i];
    path[n] = 0;
    char line[600];
    unsigned len = 0;
    unsigned which = 0;
    for (const char *f = fmt; *f && len + 2 < sizeof(line); ++f) {
        if (f[0] == '%' && f[1] == 'u') { len = AppendNumber(line, len, sizeof(line), which++ ? b : a); ++f; }
        else if (f[0] == '%' && f[1] == 's') { len = Append(line, len, sizeof(line), text); ++f; }
        else line[len++] = *f;
    }
    line[len++] = '\r';
    line[len++] = '\n';
    HANDLE h = CreateFileW(path, LogStarted ? FILE_APPEND_DATA : GENERIC_WRITE, FILE_SHARE_READ, 0,
                           LogStarted ? OPEN_ALWAYS : CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return;
    LogStarted = true;
    DWORD written = 0;
    WriteFile(h, line, len, &written, 0);
    CloseHandle(h);
}
#endif

// ================================================================ resolver
struct ImageRange { unsigned base, size; };
static const unsigned kMaxRanges = 24;
static unsigned ImageBase, ImageSize;

static unsigned ExecutableSections(ImageRange *code, unsigned *count) {
    HMODULE exe = GetModuleHandleW(0);
    *count = 0;
    if (!exe) return 0;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)exe;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    const IMAGE_SECTION_HEADER *s = IMAGE_FIRST_SECTION(nt);
    ImageBase = (unsigned)exe;
    ImageSize = nt->OptionalHeader.SizeOfImage;
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        unsigned size = s[i].Misc.VirtualSize ? s[i].Misc.VirtualSize : s[i].SizeOfRawData;
        if ((s[i].Characteristics & IMAGE_SCN_MEM_EXECUTE) && *count < kMaxRanges) {
            code[*count].base = (unsigned)exe + s[i].VirtualAddress;
            code[*count].size = size;
            ++*count;
        }
    }
    return (unsigned)exe;
}

static bool InImage(unsigned va) { return va >= ImageBase && va - ImageBase < ImageSize; }

#ifdef B200OUTFITS_TEST
__declspec(noinline)
#endif
static unsigned ScanPattern(const unsigned char *base, unsigned size, const unsigned char *pat,
                            const unsigned char *mask, unsigned len, unsigned *hits) {
    unsigned first = 0, key = 0;
    while (key < len && mask[key]) ++key;
    if (key == len || size < len) return 0;
    unsigned last = size - len;
    for (unsigned pos = 0; pos <= last; ++pos) {
        if (base[pos + key] != pat[key]) continue;
        unsigned i = 0;
        while (i < len && (mask[i] || base[pos + i] == pat[i])) ++i;
        if (i == len) {
            if (!*hits) first = (unsigned)base + pos;
            if (++*hits >= 2) return first;
        }
    }
    return first;
}

static bool Inside(const ImageRange *code, unsigned count, unsigned va, unsigned len) {
    for (unsigned r = 0; r < count; ++r)
        if (va >= code[r].base && va + len <= code[r].base + code[r].size) return true;
    return false;
}

static bool CallTarget(const ImageRange *code, unsigned count, unsigned at, unsigned *target) {
    if (!Inside(code, count, at, 5) || *(const unsigned char *)at != 0xE8) return false;
    *target = at + 5 + *(const unsigned *)(at + 1);
    return true;
}

static const unsigned kPinCount = sizeof(OUTF_PINS) / sizeof(OUTF_PINS[0]);
static unsigned PinAt[kPinCount];

// The address DrawItem's switch jumps to for `item` (its byte table, then its case table).
static unsigned DrawCase(unsigned item) {
    unsigned byteAt = SITE(DRAW_CASE_BYTES) + item - OUTF_DRAW_FIRST_CASE;
    if (!InImage(byteAt)) return 0;
    unsigned entry = SITE(DRAW_CASE_TABLE) + 4u * *(const unsigned char *)byteAt;
    if (!InImage(entry) || !InImage(entry + 3)) return 0;
    return *(const unsigned *)entry;
}

static bool Resolve() {
    static ImageRange code[kMaxRanges];
    unsigned codeCount = 0;
    if (!ExecutableSections(code, &codeCount) || !codeCount) return false;
    for (unsigned i = 0; i < kPinCount; ++i) PinAt[i] = 0;
    for (unsigned i = 0; i < kPinCount; ++i) {
        const OutfPin &pin = OUTF_PINS[i];
        if (pin.parent >= 0) continue;
        unsigned hits = 0, at = 0;
        for (unsigned r = 0; r < codeCount && hits < 2; ++r) {
            unsigned h = 0;
            unsigned found = ScanPattern((const unsigned char *)code[r].base, code[r].size, pin.bytes, pin.mask,
                                         pin.len, &h);
            if (h) { if (!hits) at = found; hits += h; }
        }
        if (hits != 1) { Log("pin %s was not found exactly once", 0, 0, pin.name); return false; }
        PinAt[i] = at;
    }
    for (unsigned pass = 0; pass < kPinCount; ++pass) {
        for (unsigned i = 0; i < kPinCount; ++i) {
            const OutfPin &pin = OUTF_PINS[i];
            if (pin.parent < 0 || PinAt[i] || !PinAt[pin.parent]) continue;
            unsigned target = 0;
            if (!CallTarget(code, codeCount, PinAt[pin.parent] + pin.call_offset, &target)) {
                Log("pin %s: its parent has no call there", 0, 0, pin.name);
                return false;
            }
            if (!Inside(code, codeCount, target, pin.len)) { Log("pin %s lies outside the code", 0, 0, pin.name); return false; }
            for (unsigned k = 0; k < pin.len; ++k) {
                if (!pin.mask[k] && ((const unsigned char *)target)[k] != pin.bytes[k]) {
                    Log("pin %s: the call target's bytes differ", 0, 0, pin.name);
                    return false;
                }
            }
            PinAt[i] = target;
        }
    }
    for (unsigned i = 0; i < kPinCount; ++i) if (!PinAt[i]) { Log("pin %s never resolved", 0, 0, OUTF_PINS[i].name); return false; }
    bool have[OUTF_SITE_COUNT];
    for (unsigned i = 0; i < OUTF_SITE_COUNT; ++i) have[i] = false;
    for (unsigned e = 0; e < sizeof(OUTF_EVIDENCE) / sizeof(OUTF_EVIDENCE[0]); ++e) {
        const OutfEvidence &ev = OUTF_EVIDENCE[e];
        unsigned at = PinAt[ev.pin] + ev.offset;
        unsigned v = ev.kind == 'L' ? at : *(const unsigned *)at;
        if (have[ev.site] && Sites[ev.site] != v) { Log("site %u: derivations disagree", ev.site); return false; }
        Sites[ev.site] = v;
        have[ev.site] = true;
    }
    for (unsigned i = 0; i < OUTF_SITE_COUNT; ++i) if (!have[i]) { Log("site %u is underived", i); return false; }
    for (unsigned c = 0; c < sizeof(OUTF_CALLS) / sizeof(OUTF_CALLS[0]); ++c) {
        const OutfCall &call = OUTF_CALLS[c];
        unsigned target = 0;
        if (!CallTarget(code, codeCount, PinAt[call.pin] + call.offset, &target)) { Log("call %u is not a call", c); return false; }
        if (target != Sites[call.function]) { Log("call %u targets another function", c); return false; }
    }
    if (!InImage(SITE(INVENTORY_MANAGER)) || !InImage(SITE(TOOL_TRAY)) || !InImage(SITE(GS_VTABLE))) {
        Log("a global lies outside the executable");
        return false;
    }
    if (!(SITE(INV_DRAW_OUTFITS) > SITE(INV_DRAW_ITEM) && SITE(INV_DRAW_OUTFITS) < SITE(INV_DRAW_ITEM) + 0x100) ||
        !(SITE(INV_TAKE_OUTFIT) > SITE(INV_TAKE_ONE) && SITE(INV_TAKE_OUTFIT) < SITE(INV_TAKE_ONE) + 0x200)) {
        Log("the outfit code is not inside DrawItem and TakeOne");
        return false;
    }
    if (DrawCase(OUTF_MALE_OUTFIT) != SITE(INV_DRAW_OUTFITS) + OUTF_DRAW_CASE_MALE ||
        DrawCase(OUTF_FEMALE_OUTFIT) != SITE(INV_DRAW_OUTFITS) + OUTF_DRAW_CASE_FEMALE) {
        Log("DrawItem does not draw the outfits from +468h / +46Ch");
        return false;
    }
    return true;
}

// ================================================================ the game
typedef bool (__thiscall *AddItemFn)(void *tray, int item, int uses);
typedef int (__thiscall *AvailableFn)(void *tray);
typedef void (__thiscall *DrawItemFn)(void *inventory, int x, int y, int item, int state, int position, int selected);
typedef void (__thiscall *SwapFn)(void *tray, int a, int b);
typedef int (__thiscall *GetOutfitFn)(void *inventory, int item);
typedef bool (__thiscall *GameStateSlotFn)(void *state, int slot);
typedef const char *(__thiscall *MakePathFn)(void *state, int slot);

// What each retargeted call called before (the game's own function).
static AddItemFn NextAddItem;
static DrawItemFn NextDrawTray;
static DrawItemFn NextDrawInHand;
static SwapFn NextSwapClick;
static SwapFn NextSwapDrop;
static GetOutfitFn NextGetOutfit;
static GameStateSlotFn NextSave;
static GameStateSlotFn NextLoad;

static unsigned char *Tray() { return (unsigned char *)SITE(TOOL_TRAY); }
static unsigned char *Inventory() { return (unsigned char *)SITE(INVENTORY_MANAGER); }
static int I32(const unsigned char *p, unsigned off) { return *(const int *)(p + off); }
static int TrayItem(unsigned place) { return I32(Tray(), place * OUTF_TRAY_PLACE_SIZE); }
static int TrayUses(unsigned place) { return I32(Tray(), place * OUTF_TRAY_PLACE_SIZE + 4); }

static bool IsOutfit(int item) { return item == (int)OUTF_MALE_OUTFIT || item == (int)OUTF_FEMALE_OUTFIT; }
static bool IsPicture(int picture) { return picture >= 0 && picture < (int)OUTF_PICTURE_LIMIT; }
static int *Field(int item) {
    return (int *)(Inventory() + (item == (int)OUTF_MALE_OUTFIT ? OUTF_INV_MALE_PICTURE : OUTF_INV_FEMALE_PICTURE));
}

// ================================================================ the pictures
// One per tray place: the outfit item it was kept for, and its picture (-1: not known, the stock one).
struct Place { int item; int picture; };
static Place Places[OUTF_TRAY_PLACES];

static void CountKnown() {
    unsigned n = 0;
    for (unsigned k = 0; k < OUTF_TRAY_PLACES; ++k) if (Places[k].picture >= 0) ++n;
    B200Outfits_Status.known = n;
}

static void Forget() {
    for (unsigned k = 0; k < OUTF_TRAY_PLACES; ++k) { Places[k].item = 0; Places[k].picture = -1; }
    CountKnown();
}

// A place that no longer holds the outfit its picture was kept for (used up, thrown out, a new family, a
// load) forgets it.
static void Sweep() {
    bool changed = false;
    for (unsigned k = 0; k < OUTF_TRAY_PLACES; ++k) {
        if (Places[k].picture >= 0 && Places[k].item != TrayItem(k)) {
            Places[k].item = 0;
            Places[k].picture = -1;
            changed = true;
        }
    }
    if (changed) CountKnown();
}

// The place's own picture, or -1 when it is not known or the place does not hold that outfit now.
static int PictureOf(int place, int item) {
    if (place < 0 || place >= (int)OUTF_TRAY_PLACES || !IsOutfit(item)) return -1;
    const Place &p = Places[place];
    if (p.item != item || TrayItem((unsigned)place) != item || !IsPicture(p.picture)) return -1;
    return p.picture;
}

// ================================================================ hooks
// The store's buy: AddItem(item, uses) fills the first free place (GetAvailableSlot), and the picture just
// bought is in +468h / +46Ch (TakeOne ran right before it, in the same run of HandlePurchaseItem).
static bool __fastcall BuyAddItem(void *tray, void *, int item, int uses) {
    Sweep();
    int place = ((AvailableFn)SITE(TT_AVAILABLE))(tray);
    bool ok = NextAddItem(tray, item, uses);
    if (ok && place >= 0 && place < (int)OUTF_TRAY_PLACES && TrayItem((unsigned)place) == item) {
        Place &p = Places[place];
        p.item = item;
        p.picture = -1;
        if (IsOutfit(item) && IsPicture(*Field(item))) p.picture = *Field(item);
        CountKnown();
    }
    return ok;
}

// Draws through `next` with the place's own picture lent to the outfit's field for this one call.
static void DrawPlace(DrawItemFn next, void *inventory, int place, int x, int y, int item, int state, int position,
                      int selected) {
    int picture = PictureOf(place, item);
    if (picture < 0) { next(inventory, x, y, item, state, position, selected); return; }
    int *field = Field(item);
    int kept = *field;
    *field = picture;
    ++B200Outfits_Status.lent;
    next(inventory, x, y, item, state, position, selected);
    *field = kept;
}

// CToolTray::Draw draws place k at x = +7Ch + h/2, y = +80h + h*k + h/2 + 6 (h = +78h); the place is read
// back from the point, and only a point that is exactly a place of the tray, holding this item, counts.
static int TrayPlaceAt(int x, int y, int item) {
    const unsigned char *t = Tray();
    int h = I32(t, OUTF_TRAY_HEIGHT);
    int count = I32(t, OUTF_TRAY_COUNT);
    if (h <= 0 || count <= 0) return -1;
    int half = h / 2;
    if (x != I32(t, OUTF_TRAY_LEFT) + half) return -1;
    int rel = y - I32(t, OUTF_TRAY_TOP) - half - (int)OUTF_TRAY_DRAW_OFFSET;
    if (rel < 0 || rel % h) return -1;
    int place = rel / h;
    if (place >= count || place >= (int)OUTF_TRAY_PLACES || TrayItem((unsigned)place) != item) return -1;
    return place;
}

static void __fastcall DrawTray(void *inventory, void *, int x, int y, int item, int state, int position, int selected) {
    Sweep();
    DrawPlace(NextDrawTray, inventory, TrayPlaceAt(x, y, item), x, y, item, state, position, selected);
}

// CToolTray::DrawToolInHand draws the place in the hand (+A0h) at the cursor.
static void __fastcall DrawInHand(void *inventory, void *, int x, int y, int item, int state, int position, int selected) {
    Sweep();
    DrawPlace(NextDrawInHand, inventory, I32(Tray(), OUTF_TRAY_HELD), x, y, item, state, position, selected);
}

// CToolTray::SwapSlots(a, b) swaps two places when a, b != -1, a != b and both >= 2: the pictures go with
// them, exactly when the places do.
static void SwapPlaces(SwapFn next, void *tray, int a, int b) {
    Sweep();
    bool swaps = a != -1 && b != -1 && a != b && a >= (int)OUTF_TRAY_FIRST_FREE && b >= (int)OUTF_TRAY_FIRST_FREE;
    next(tray, a, b);
    if (swaps && a < (int)OUTF_TRAY_PLACES && b < (int)OUTF_TRAY_PLACES) {
        Place t = Places[a];
        Places[a] = Places[b];
        Places[b] = t;
    }
    Sweep();
}

static void __fastcall SwapClick(void *tray, void *, int a, int b) { SwapPlaces(NextSwapClick, tray, a, b); }
static void __fastcall SwapDrop(void *tray, void *, int a, int b) { SwapPlaces(NextSwapDrop, tray, a, b); }

// Putting an outfit on: the villager's body is set to GetOutfit(49h / 4Ah) while the outfit is in use in
// the hand (+A5h, place +A0h; UseTool spends that place right after). A stock outfit with a kept picture
// gives that picture; anything else (an expansion outfit or a hairstyle in the hand, which the game reports
// as the stock tool, or a picture not known) is the executable's own answer.
static int __fastcall PutOn(void *inventory, void *, int item) {
    Sweep();
    const unsigned char *t = Tray();
    if (t[OUTF_TRAY_IN_USE]) {
        int picture = PictureOf(I32(t, OUTF_TRAY_HELD), item);
        if (picture >= 0) {
            ++B200Outfits_Status.applied;
            return picture;
        }
    }
    return NextGetOutfit(inventory, item);
}

// ================================================================ the sidecar
// Little-endian, all fields 32-bit unless said otherwise (188 bytes):
//   0  "VF2OUTFT"          8  version (1)       12 "VF2B200\0"        20 file size
//   24 save file FNV-1a 64 (8)                 32 save file size
//   36 what it describes: the tray's 9 places as the save holds them (item, uses; an item LoadState would
//      not keep is 0), then CInventoryManager +450h .. +470h (the store's six pictures, the two last
//      bought, the redraw time): 108 bytes
//   144 the 9 places' pictures (-1: not known)
//   180 the FNV-1a 64 of every byte before it (8).
static const unsigned kBind = 36;
static const unsigned kBindSize = OUTF_TRAY_PLACES * 8 + OUTF_INV_BIND_COUNT * 4;
static const unsigned kPictures = kBind + kBindSize;
static const unsigned kFileSize = kPictures + OUTF_TRAY_PLACES * 4 + 8;
static unsigned char FileBuffer[kFileSize];
static unsigned char ReadBuffer[0x10000];

struct Sidecar {
    unsigned long long saveHash;
    unsigned saveSize;
    unsigned char bind[kBindSize];
    int pictures[OUTF_TRAY_PLACES];
};
static Sidecar Loaded;

static const unsigned long long kFnvBasis = 0xCBF29CE484222325ull;
static const unsigned long long kFnvPrime = 0x100000001B3ull;

static unsigned long long Fnv(unsigned long long h, const unsigned char *p, unsigned n) {
    for (unsigned i = 0; i < n; ++i) { h ^= p[i]; h *= kFnvPrime; }
    return h;
}

static void Put32(unsigned char *p, unsigned v) { p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8); p[2] = (unsigned char)(v >> 16); p[3] = (unsigned char)(v >> 24); }
static unsigned Get32(const unsigned char *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((unsigned)p[3] << 24); }

// The state a sidecar describes, as it is in memory now. After a save it is what the save holds; after a
// load it is what the load made of it (CToolTray::LoadState keeps an item 0..E0h and makes anything else
// 0, and CInventoryManager::LoadState copies +450h .. +470h back as they were).
static void Binding(unsigned char *out) {
    for (unsigned k = 0; k < OUTF_TRAY_PLACES; ++k) {
        int item = TrayItem(k);
        if (item < 0 || item >= (int)OUTF_TRAY_ITEM_LIMIT) item = 0;
        Put32(out + k * 8, (unsigned)item);
        Put32(out + k * 8 + 4, (unsigned)TrayUses(k));
    }
    for (unsigned f = 0; f < OUTF_INV_BIND_COUNT; ++f)
        Put32(out + OUTF_TRAY_PLACES * 8 + f * 4, (unsigned)I32(Inventory(), OUTF_INV_BIND_FIRST + f * 4));
}

static bool Binds(const Sidecar &file) {
    static unsigned char now[kBindSize];
    Binding(now);
    for (unsigned i = 0; i < kBindSize; ++i) if (now[i] != file.bind[i]) return false;
    return true;
}

// What reading a file found. FILE_SHUT: it is there but could not be opened or read (another program
// holds it: a backup tool, a virus scan, a cloud sync). A shut file is never judged damaged, never set
// aside and never replaced; only a file that opened and then failed validation is damaged.
enum { FILE_MISSING = 0, FILE_OK = 1, FILE_DAMAGED = -1, FILE_SHUT = -2, FILE_FOREIGN = -3 };

static const unsigned kOpenTries = 5;          // about a second in all
static const DWORD kOpenWaitMs = 250;

static bool Transient(DWORD e) {
    return e == ERROR_SHARING_VIOLATION || e == ERROR_LOCK_VIOLATION || e == ERROR_ACCESS_DENIED;
}

// Opens for reading, trying a file another program holds open again a few times.
static HANDLE OpenForRead(const char *path, DWORD *error) {
    for (unsigned k = 0;; ++k) {
        HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
        if (h != INVALID_HANDLE_VALUE) { *error = 0; return h; }
        DWORD e = GetLastError();
        if (!Transient(e) || k + 1 >= kOpenTries) { *error = e; return h; }
        Sleep(kOpenWaitMs);
    }
}

static int OpenFailure(DWORD e) {
    return e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND ? FILE_MISSING : FILE_SHUT;
}

static int HashFile(const char *path, unsigned long long *hash, unsigned *size) {
    DWORD error = 0;
    HANDLE h = OpenForRead(path, &error);
    if (h == INVALID_HANDLE_VALUE) return OpenFailure(error);
    unsigned long long v = kFnvBasis;
    unsigned total = 0;
    int r = FILE_OK;
    for (;;) {
        DWORD got = 0;
        if (!ReadFile(h, ReadBuffer, sizeof(ReadBuffer), &got, 0)) { r = FILE_SHUT; break; }
        if (!got) break;
        v = Fnv(v, ReadBuffer, got);
        total += got;
    }
    CloseHandle(h);
    *hash = v;
    *size = total;
    return r;
}

// Every sidecar path buffer: SidecarPath refuses a path that does not fit.
static const unsigned kSidecarPathCap = MAX_PATH + 64;

static unsigned Length(const char *s) { unsigned n = 0; while (s[n]) ++n; return n; }

// The sidecar of the save file the game uses for `slot`: <save folder>\Virtual Families 2 Patcher
// Data\Outfits\<save file name>.dat. `folder` (optional) receives the Outfits folder.
static bool SidecarPath(void *state, int slot, char *out, unsigned cap, char *saveOut, char *folder) {
    if (!state) return false;
    void **vtable = *(void ***)state;
    const char *save = ((MakePathFn)vtable[OUTF_LDW_PATH_VSLOT / 4])(state, slot);
    if (!save) return false;
    unsigned n = Length(save);
    if (n == 0 || n + 1 >= MAX_PATH) return false;
    if (saveOut) Copy(saveOut, save, n + 1);
    unsigned cut = n;
    while (cut > 0 && save[cut - 1] != '\\' && save[cut - 1] != '/') --cut;
    if (cut == 0 || cut == n) return false;
    static const char middle[] = "Virtual Families 2 Patcher Data\\Outfits\\";
    unsigned m = sizeof(middle) - 1;
    if (n + m + 5 >= cap) return false;
    Copy(out, save, cut);
    Copy(out + cut, middle, m);
    if (folder) {
        Copy(folder, out, cut + m - 1);
        folder[cut + m - 1] = 0;
    }
    Copy(out + cut + m, save + cut, n - cut);
    Copy(out + cut + m + (n - cut), ".dat", 5);
    return true;
}

static void EnsureFolders(const char *outfits) {
    char path[MAX_PATH];
    unsigned n = Length(outfits);
    if (n + 1 >= MAX_PATH) return;
    Copy(path, outfits, n + 1);
    unsigned cut = n;
    while (cut > 0 && path[cut - 1] != '\\') --cut;
    if (cut > 1) {
        path[cut - 1] = 0;
        CreateDirectoryA(path, 0);       // the Patcher Data folder (an existing one is fine)
        path[cut - 1] = '\\';
    }
    CreateDirectoryA(path, 0);
}

// FILE_OK (read and valid), FILE_MISSING, FILE_DAMAGED (opened, failed validation) or FILE_SHUT.
static int ReadSidecar(const char *path, Sidecar *out) {
    DWORD error = 0;
    HANDLE h = OpenForRead(path, &error);
    if (h == INVALID_HANDLE_VALUE) return OpenFailure(error);
    DWORD got = 0;
    BOOL ok = ReadFile(h, FileBuffer, kFileSize, &got, 0);
    DWORD more = 0;
    unsigned char extra[1];
    BOOL okMore = TRUE;
    if (ok && got == kFileSize) okMore = ReadFile(h, extra, 1, &more, 0);
    CloseHandle(h);
    if (!ok || !okMore) return FILE_SHUT;
    if (more || got != kFileSize) return FILE_DAMAGED;
    static const unsigned char magic[8] = { 'V', 'F', '2', 'O', 'U', 'T', 'F', 'T' };
    static const unsigned char tag[8] = { 'V', 'F', '2', 'B', '2', '0', '0', 0 };
    for (unsigned k = 0; k < 8; ++k) if (FileBuffer[k] != magic[k] || FileBuffer[12 + k] != tag[k]) return FILE_DAMAGED;
    if (Get32(FileBuffer + 8) != OUTF_SIDECAR_VERSION || Get32(FileBuffer + 20) != kFileSize) return FILE_DAMAGED;
    unsigned long long sum = Fnv(kFnvBasis, FileBuffer, kFileSize - 8);
    if (Get32(FileBuffer + kFileSize - 8) != (unsigned)sum || Get32(FileBuffer + kFileSize - 4) != (unsigned)(sum >> 32))
        return FILE_DAMAGED;
    out->saveHash = Get32(FileBuffer + 24) | ((unsigned long long)Get32(FileBuffer + 28) << 32);
    out->saveSize = Get32(FileBuffer + 32);
    Copy(out->bind, FileBuffer + kBind, kBindSize);
    for (unsigned k = 0; k < OUTF_TRAY_PLACES; ++k) {
        int item = (int)Get32(FileBuffer + kBind + k * 8);
        int picture = (int)Get32(FileBuffer + kPictures + k * 4);
        // A picture only for an outfit place, and only a body row: anything else is not this format.
        if (picture != -1 && (!IsOutfit(item) || !IsPicture(picture))) return FILE_DAMAGED;
        out->pictures[k] = picture;
    }
    return FILE_OK;
}

static bool AnyKnown() {
    for (unsigned k = 0; k < OUTF_TRAY_PLACES; ++k) if (PictureOf((int)k, TrayItem(k)) >= 0) return true;
    return false;
}

static bool WriteSidecar(const char *path, const char *folder, unsigned long long saveHash, unsigned saveSize) {
    Zero(FileBuffer, kFileSize);
    Copy(FileBuffer, "VF2OUTFT", 8);
    Put32(FileBuffer + 8, OUTF_SIDECAR_VERSION);
    Copy(FileBuffer + 12, "VF2B200\0", 8);
    Put32(FileBuffer + 20, kFileSize);
    Put32(FileBuffer + 24, (unsigned)saveHash);
    Put32(FileBuffer + 28, (unsigned)(saveHash >> 32));
    Put32(FileBuffer + 32, saveSize);
    Binding(FileBuffer + kBind);
    for (unsigned k = 0; k < OUTF_TRAY_PLACES; ++k)
        Put32(FileBuffer + kPictures + k * 4, (unsigned)PictureOf((int)k, TrayItem(k)));
    unsigned long long sum = Fnv(kFnvBasis, FileBuffer, kFileSize - 8);
    Put32(FileBuffer + kFileSize - 8, (unsigned)sum);
    Put32(FileBuffer + kFileSize - 4, (unsigned)(sum >> 32));
    EnsureFolders(folder);
    char temp[kSidecarPathCap + 8];
    unsigned n = Length(path);
    if (n + 5 > sizeof(temp)) return false;
    Copy(temp, path, n);
    Copy(temp + n, ".tmp", 5);
    HANDLE h = CreateFileA(temp, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    BOOL ok = WriteFile(h, FileBuffer, kFileSize, &written, 0) && written == kFileSize;
    if (ok) ok = FlushFileBuffers(h);
    CloseHandle(h);
    if (!ok) { DeleteFileA(temp); return false; }
    if (!MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) { DeleteFileA(temp); return false; }
    return true;
}

// A damaged or foreign sidecar is kept, renamed beside itself: "<name>.unreadable-N.dat".
// True when the file is now beside itself; false leaves it exactly where it was (it is never deleted).
static bool MoveAside(const char *path) {
    // "<path less .dat>.unreadable-NNN.dat": the path plus 16 characters at most, and the nul.
    char aside[kSidecarPathCap + 32];
    unsigned n = Length(path);
    if (n < 4 || n + 17 > sizeof(aside)) return false;
    Copy(aside, path, n - 4);
    for (unsigned k = 1; k < 1000; ++k) {
        unsigned m = n - 4;
        static const char mid[] = ".unreadable-";
        Copy(aside + m, mid, sizeof(mid) - 1);
        m += sizeof(mid) - 1;
        char digits[4];
        unsigned d = 0, v = k;
        do { digits[d++] = (char)('0' + v % 10); v /= 10; } while (v);
        while (d) aside[m++] = digits[--d];
        Copy(aside + m, ".dat", 5);
        if (MoveFileExA(path, aside, 0)) return true;
        if (GetLastError() != ERROR_ALREADY_EXISTS && GetLastError() != ERROR_FILE_EXISTS) return false;
    }
    return false;
}

// The file's pictures become the tray's (the file describes the tray exactly as it is now).
static void Adopt(const Sidecar &file) {
    Forget();
    for (unsigned k = 0; k < OUTF_TRAY_PLACES; ++k) {
        int item = TrayItem(k);
        if (file.pictures[k] >= 0 && IsOutfit(item)) {
            Places[k].item = item;
            Places[k].picture = file.pictures[k];
        }
    }
    CountKnown();
}

// FILE_OK only when the sidecar validates and was written with `save` as it is on disk now; FILE_FOREIGN
// when it validates but belongs to another save (or to none); FILE_SHUT when either could not be read.
static int Describes(const Sidecar &file, const char *save) {
    unsigned long long hash = 0;
    unsigned size = 0;
    int h = HashFile(save, &hash, &size);
    if (h == FILE_SHUT) return FILE_SHUT;
    return h == FILE_OK && file.saveHash == hash && file.saveSize == size ? FILE_OK : FILE_FOREIGN;
}

static int Classify(const char *path, const char *save, Sidecar *out) {
    int r = ReadSidecar(path, out);
    return r == FILE_OK ? Describes(*out, save) : r;
}

// A load found this slot's sidecar shut: it is unread, and no save replaces or moves it until it is read.
static int ShutSlot = -1;

static void AfterLoad(void *state, int slot) {
    char path[kSidecarPathCap], save[MAX_PATH], folder[kSidecarPathCap];
    char backup[kSidecarPathCap], backupSave[MAX_PATH];
    ShutSlot = -1;
    B200Outfits_Status.lastLoad = 4;
    if (!SidecarPath(state, slot, path, sizeof(path), save, folder)) return;
    unsigned long long hash = 0;
    unsigned size = 0;
    bool hashed = HashFile(save, &hash, &size) == FILE_OK;
    int r = ReadSidecar(path, &Loaded);
    if (r == FILE_SHUT) {
        // Held open by another program: not damaged. It is left exactly as it is, and never replaced.
        ShutSlot = slot;
        B200Outfits_Status.lastLoad = 6;
        Log("slot %u: the sidecar could not be opened (in use?); it is left as it is", (unsigned)slot);
    } else if (r == FILE_DAMAGED) {
        bool moved = MoveAside(path);
        B200Outfits_Status.lastLoad = moved ? 5 : 7;
        Log(moved ? "slot %u: an unreadable sidecar was moved aside"
                  : "slot %u: an unreadable sidecar could not be moved aside; it is left as it is", (unsigned)slot);
    }
    if (r == FILE_OK && hashed && Loaded.saveHash == hash && Loaded.saveSize == size && Binds(Loaded)) {
        Adopt(Loaded);
        B200Outfits_Status.lastLoad = 1;
        Log("slot %u: %u outfit pictures from the sidecar", (unsigned)slot, B200Outfits_Status.known);
        return;
    }
    // The game's own backup (slot + 20) is the previous save: a restored backup has its sidecar there.
    static Sidecar backupFile;
    if (hashed && SidecarPath(state, slot + (int)OUTF_SAVE_BACKUP_OFFSET, backup, sizeof(backup), backupSave, 0)
        && ReadSidecar(backup, &backupFile) == FILE_OK && backupFile.saveHash == hash && backupFile.saveSize == size
        && Binds(backupFile)) {
        Adopt(backupFile);
        if (r != FILE_SHUT) B200Outfits_Status.lastLoad = 2;
        Log("slot %u: %u outfit pictures from the backup's sidecar", (unsigned)slot, B200Outfits_Status.known);
        return;
    }
    // The same save changed by a tool that leaves the tray and the outfits alone (Rename Family, Game Speed):
    // the file no longer hashes the same, but the tray and every outfit field are exactly the ones it describes.
    if (r == FILE_OK && Binds(Loaded)) {
        Adopt(Loaded);
        B200Outfits_Status.lastLoad = 3;
        Log("slot %u: %u outfit pictures from the sidecar of this tray (the save file was changed)",
            (unsigned)slot, B200Outfits_Status.known);
    }
}

static bool __fastcall LoadHook(void *state, void *, int slot) {
    if (slot <= 0) return NextLoad(state, slot);            // the settings file
    // Whatever the load makes of the tray, the pictures held now are not that save's.
    Forget();
    bool loaded = NextLoad(state, slot);
    if (loaded) AfterLoad(state, slot);
    return loaded;
}

// Before the game's own save rotates its files (it removes the save at slot + 20 and renames this slot's
// save to it), the two sidecars are checked. Only a sidecar that validated and belongs to its save is
// rotated with it (or removed with it); a damaged or foreign one is set aside; a shut one is left as it is,
// and while this slot's is shut no sidecar is written for it. Returns false when none may be written.
static bool RotateSidecars(int slot, const char *path, const char *save, const char *backup, const char *backupSave) {
    static Sidecar mineFile, oldFile;
    int mine = Classify(path, save, &mineFile);
    // Written with the save now at slot + 20 (a save was made while it was shut): it goes with that save.
    bool backups = mine == FILE_FOREIGN && Describes(mineFile, backupSave) == FILE_OK;
    // First read since the load found it shut: it is a sidecar of the save on disk, so it rotates with it
    // (its pictures were never used: this session showed the stock ones for those places).
    if (ShutSlot == slot && mine != FILE_SHUT) ShutSlot = -1;
    if (mine == FILE_SHUT || ShutSlot == slot) {
        Log("slot %u: the sidecar could not be opened (in use?); it is left as it is", (unsigned)slot);
        return false;
    }
    int old = Classify(backup, backupSave, &oldFile);
    bool clear = old == FILE_MISSING;
    if (old == FILE_OK) clear = DeleteFileA(backup) != 0;       // its save is the one the game removes now
    else if (old == FILE_DAMAGED || old == FILE_FOREIGN) clear = MoveAside(backup);
    // old == FILE_SHUT: the backup's sidecar is left as it is
    if (mine == FILE_OK) {
        if (clear) MoveFileExA(path, backup, 0);
    } else if (backups) {
        DeleteFileA(path);                                       // validated, and its save is removed now
    } else if (mine == FILE_DAMAGED || mine == FILE_FOREIGN) {
        if (!MoveAside(path)) {
            Log("slot %u: a sidecar could not be moved aside; it is left as it is", (unsigned)slot);
            return false;
        }
    }
    return true;
}

static bool __fastcall SaveHook(void *state, void *, int slot) {
    if (slot <= 0) return NextSave(state, slot);            // the settings file
    Sweep();
    char path[kSidecarPathCap], save[MAX_PATH], folder[kSidecarPathCap];
    char backup[kSidecarPathCap], backupSave[MAX_PATH];
    bool named = SidecarPath(state, slot, path, sizeof(path), save, folder)
        && SidecarPath(state, slot + (int)OUTF_SAVE_BACKUP_OFFSET, backup, sizeof(backup), backupSave, 0);
    bool writable = named && RotateSidecars(slot, path, save, backup, backupSave);
    bool saved = NextSave(state, slot);
    if (!saved || !named) return saved;
    if (!writable) { B200Outfits_Status.lastSave = 4; return saved; }
    if (!AnyKnown()) { B200Outfits_Status.lastSave = 2; return saved; }
    unsigned long long hash = 0;
    unsigned size = 0;
    if (HashFile(save, &hash, &size) == FILE_OK && WriteSidecar(path, folder, hash, size)) {
        B200Outfits_Status.lastSave = 1;
    } else {
        B200Outfits_Status.lastSave = 3;
        Log("slot %u: the sidecar could not be written", (unsigned)slot);
    }
    return saved;
}

// ================================================================ plan and install
static const unsigned kMaxWrites = 12;

struct HookWrite {
    unsigned va;
    unsigned len;          // 5 (a call) or 4 (a vtable slot)
    bool data;
    unsigned char bytes[5];
    unsigned char original[5];
};

struct Plan {
    HookWrite writes[kMaxWrites];
    unsigned count;
};

static void *CallHandler(unsigned site) {
    switch (site) {
    case OUTF_SITE_CALL_BUY_ADD: return (void *)&BuyAddItem;
    case OUTF_SITE_CALL_DRAW_TRAY: return (void *)&DrawTray;
    case OUTF_SITE_CALL_DRAW_IN_HAND: return (void *)&DrawInHand;
    case OUTF_SITE_CALL_SWAP_CLICK: return (void *)&SwapClick;
    case OUTF_SITE_CALL_SWAP_DROP: return (void *)&SwapDrop;
    case OUTF_SITE_CALL_APPLY_MALE: return (void *)&PutOn;
    case OUTF_SITE_CALL_APPLY_FEMALE: return (void *)&PutOn;
    }
    return 0;
}

static void SetCallNext(unsigned site, unsigned target) {
    switch (site) {
    case OUTF_SITE_CALL_BUY_ADD: NextAddItem = (AddItemFn)target; break;
    case OUTF_SITE_CALL_DRAW_TRAY: NextDrawTray = (DrawItemFn)target; break;
    case OUTF_SITE_CALL_DRAW_IN_HAND: NextDrawInHand = (DrawItemFn)target; break;
    case OUTF_SITE_CALL_SWAP_CLICK: NextSwapClick = (SwapFn)target; break;
    case OUTF_SITE_CALL_SWAP_DROP: NextSwapDrop = (SwapFn)target; break;
    case OUTF_SITE_CALL_APPLY_MALE: NextGetOutfit = (GetOutfitFn)target; break;
    case OUTF_SITE_CALL_APPLY_FEMALE: NextGetOutfit = (GetOutfitFn)target; break;
    }
}

static HookWrite *AddWrite(Plan &plan, unsigned va, unsigned len, bool data) {
    if (plan.count >= kMaxWrites) return 0;
    HookWrite &w = plan.writes[plan.count++];
    Zero(&w, sizeof(w));
    w.va = va;
    w.len = len;
    w.data = data;
    return &w;
}

// A vtable slot holds the stock function, or a handler outside the executable (another companion DLL's):
// either is chained to.
static bool SlotChain(unsigned slotVa, unsigned stock, unsigned *now) {
    *now = *(const unsigned *)slotVa;
    return *now == stock || (*now && !InImage(*now));
}

// Builds every write (nothing of the game is written here).
static bool PlanHooks(Plan &plan) {
    plan.count = 0;
    for (unsigned h = 0; h < sizeof(OUTF_CALL_HOOKS) / sizeof(OUTF_CALL_HOOKS[0]); ++h) {
        const OutfCallHook &hook = OUTF_CALL_HOOKS[h];
        unsigned site = Sites[hook.site];
        void *handler = CallHandler(hook.site);
        if (!handler || *(const unsigned char *)site != 0xE8) return false;
        unsigned target = site + 5 + *(const unsigned *)(site + 1);
        if (target != Sites[hook.function]) return false;     // another DLL took this call: leave it alone
        SetCallNext(hook.site, target);
        HookWrite *w = AddWrite(plan, site, 5, false);
        if (!w) return false;
        w->bytes[0] = 0xE8;
        *(int *)(w->bytes + 1) = (int)((unsigned)handler - (site + 5));
    }
    unsigned vt = SITE(GS_VTABLE);
    unsigned load = 0, save = 0;
    if (!SlotChain(vt + OUTF_GS_LOAD_VSLOT, SITE(GS_LOAD), &load)) return false;
    if (!SlotChain(vt + OUTF_GS_SAVE_VSLOT, SITE(GS_SAVE), &save)) return false;
    NextLoad = (GameStateSlotFn)load;
    NextSave = (GameStateSlotFn)save;
    HookWrite *wl = AddWrite(plan, vt + OUTF_GS_LOAD_VSLOT, 4, true);
    if (!wl) return false;
    *(unsigned *)wl->bytes = (unsigned)&LoadHook;
    HookWrite *ws = AddWrite(plan, vt + OUTF_GS_SAVE_VSLOT, 4, true);
    if (!ws) return false;
    *(unsigned *)ws->bytes = (unsigned)&SaveHook;
    return true;
}

// 0 = setting off (nothing planned); -1 = could not be proved (nothing planned); 1 = planned.
static int BuildPlan(bool enabled, Plan &plan) {
    plan.count = 0;
    if (!enabled) return 0;
    if (!Resolve()) return -1;
    if (!PlanHooks(plan)) { Log("the hooks could not be planned"); return -1; }
    return 1;
}

static bool WriteCode(const HookWrite &w, const unsigned char *bytes) {
    DWORD old = 0;
    if (!VirtualProtect((void *)w.va, w.len, w.data ? PAGE_READWRITE : PAGE_EXECUTE_READWRITE, &old)) return false;
    for (unsigned i = 0; i < w.len; ++i) ((volatile unsigned char *)w.va)[i] = bytes[i];
    DWORD ignored = 0;
    BOOL restored = VirtualProtect((void *)w.va, w.len, old, &ignored);
    if (!w.data) FlushInstructionCache(GetCurrentProcess(), (void *)w.va, w.len);
    return restored != FALSE;
}

// All or nothing.
static bool Apply(Plan &plan) {
    for (unsigned i = 0; i < plan.count; ++i) {
        HookWrite &w = plan.writes[i];
        for (unsigned j = 0; j < w.len; ++j) w.original[j] = ((const unsigned char *)w.va)[j];
        if (!WriteCode(w, w.bytes)) {
            Log("write %u failed; restoring the earlier writes", i);
            for (unsigned j = 0; j < i; ++j) WriteCode(plan.writes[j], plan.writes[j].original);
            B200Outfits_Status.writeMask = 0;
            return false;
        }
        B200Outfits_Status.writeMask |= 1u << i;
    }
    return true;
}

static bool SettingOn() {
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    while (Folder[n] && n + 16 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *name = L"vf2outfits.ini";
    for (unsigned i = 0; name[i]; ++i) path[n++] = name[i];
    path[n] = 0;
    return GetPrivateProfileIntW(L"Patches", L"OutfitPictures", 0, path) == 1;
}

// Called once by the executable's loader, before the game loop starts.
extern "C" __declspec(dllexport) void __cdecl B200Outfits_Startup() {
    static bool started = false;
    if (started) return;
    started = true;
    DWORD n = GetModuleFileNameW(ThisModule, Folder, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    unsigned cut = n;
    while (cut > 0 && Folder[cut - 1] != L'\\') --cut;
    if (!cut) return;
    Folder[cut] = 0;
    Log("vf2outfits_b200 started");
    bool on = SettingOn();
    B200Outfits_Status.requested = on ? 1u : 0u;
    static Plan plan;
    int built = BuildPlan(on, plan);
    if (built == 0) { Log("Outfit Pictures is off: the game is stock"); return; }
    if (built < 0) { Log("the executable could not be proved: installing nothing"); return; }
    B200Outfits_Status.resolved = 1;
    Forget();
    if (Apply(plan)) {
        B200Outfits_Status.installed = 1;
        Log("Outfit Pictures installed (%u writes)", plan.count);
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        ThisModule = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}

// ---------------------------------------------------------------- test builds only
#ifdef B200OUTFITS_TEST
extern "C" __declspec(dllexport) unsigned __cdecl B200Outfits_TestScanAddress() { return (unsigned)&ScanPattern; }
extern "C" __declspec(dllexport) void __cdecl B200Outfits_TestSetModule(unsigned module) { ThisModule = (HMODULE)module; }
extern "C" __declspec(dllexport) void __cdecl B200Outfits_TestSites(unsigned *out) {
    for (unsigned i = 0; i < OUTF_SITE_COUNT; ++i) out[i] = Sites[i];
}
// Plans without writing. out: [status, count, then per write: va, len, data, bytes0..3, byte4].
extern "C" __declspec(dllexport) int __cdecl B200Outfits_TestPlan(int enabled, unsigned *out) {
    static Plan plan;
    int built = BuildPlan(enabled != 0, plan);
    out[0] = (unsigned)built;
    out[1] = built > 0 ? plan.count : 0;
    for (unsigned i = 0; built > 0 && i < plan.count; ++i) {
        out[2 + i * 5 + 0] = plan.writes[i].va;
        out[2 + i * 5 + 1] = plan.writes[i].len;
        out[2 + i * 5 + 2] = plan.writes[i].data ? 1u : 0u;
        out[2 + i * 5 + 3] = *(unsigned *)plan.writes[i].bytes;
        out[2 + i * 5 + 4] = plan.writes[i].bytes[4];
    }
    if (built > 0) Forget();
    return built;
}
// The pictures kept: out[k * 2] = item, out[k * 2 + 1] = picture, for the 9 places.
extern "C" __declspec(dllexport) void __cdecl B200Outfits_TestPlaces(int *out) {
    for (unsigned k = 0; k < OUTF_TRAY_PLACES; ++k) {
        out[k * 2] = Places[k].item;
        out[k * 2 + 1] = Places[k].picture;
    }
}
#endif
