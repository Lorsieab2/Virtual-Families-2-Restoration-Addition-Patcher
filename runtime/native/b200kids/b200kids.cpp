// vf2kids_b200.dll -- "Up to 28 Children", the companion DLL for the B200 Virtual Families 2
// executable. One feature, one DLL: nothing else is installed here.
//
// What it does (the owner's request): a generation may have up to 28 children instead of 6. Only
// the first 6 appear in the Family Tree, exactly as now, and every child -- including the 7th to
// the 28th -- can be chosen to inherit the house in Next Generation. Twins and triplets near the
// limit are clamped by the game's own rule (see EmptyOffspringSlots below), so the total never
// exceeds 28 and no baby is ever made without a place to record it.
//
// Why 28: the household is the 30 ordinary villager slots of CVillagerManager (2 parents + 28
// children). The stock Family Tree record holds exactly 6 children (0x1B8 + 6 * 0xD8 = 0x6C8, the
// size of one generation record): a 7th written there would overwrite the next generation's record,
// and the save file has no room for more (the 30 records fill the save block exactly). So the stock
// record keeps the first 6 untouched, and children 7..28 are kept by this DLL in a sidecar .dat
// file beside each save file ("Virtual Families 2 Patcher Data\Children\<save file>.dat"). The save
// format is not changed: the extra children are ordinary villagers the stock save already stores
// (all 30 slots are saved); the sidecar only remembers that they are children of this generation.
//
// The B200 executable is RELOCATED (DYNAMICBASE) and each of the 32 matrix variants links to
// different addresses, so this DLL holds NO game address. b200kids_sites.h (generated and proved by
// runtime/tools/gen_b200_kids_sites.py) holds whole stock functions of the core variant with
// wildcards where a relocated field or a call displacement sits; Resolve() finds every one in the
// live image exactly once and derives each address from where they were found.
//
// The executable's dormant loader (.vf2kids byte, 0 as built) loads this DLL only when the patcher
// setting is on, after the Time Controls DLL, and calls B200Kids_Startup() once before the game
// loop. Installing is: setting -> resolve -> plan -> apply, all or nothing. With the setting off,
// or anything the resolver cannot prove, NOTHING is written and the game is B200's own bytes.
//
// The entry hooks (each a 5-byte jmp; "wrap" hooks hand the call to the stock function through a
// trampoline of its own first whole, position-independent instructions):
//
//   CFamilyTree::EmptyOffspringSlots  replaced: min(28 - children recorded so far (6 stock + extra,
//                                     living or not, exactly as the stock count), free household
//                                     slots). Impregnate asks this first and allows twins only when it
//                                     is > 1 and triplets only when it is > 2, B200's forced-count
//                                     cheat clamps to it, and every adoption/spawn asks it, so 27
//                                     children allow one more baby, 26 two, 28 none. Stock odds are
//                                     unchanged whenever there is room.
//   CFamilyTree::AddOffspring         stock below 6; at 6 the child is recorded here (a sidecar
//                                     entry: slot, gender, name), never in the stock record.
//   CFamilyTree::CountSurvivingChildren  stock + living extra children (same "active" test).
//   CFamilyTree::ReportDeath          marks an extra child dead first, then the stock function runs
//                                     (it recounts survivors through the hook above).
//   CFamilyTree::ChangeName           follows a rename of an extra child.
//   CFamilyTree::Reset                clears the extra children (load, Evict Family).
//   CFamilyTree::StartNextGeneration  a new generation starts with no extra children.
//   CAdoptionScene::CreateNextGenerationCandidates / GetNextCandidate
//                                     stock when no extra child exists. Otherwise every child is a
//                                     candidate: they are cloned as adults ONE AT A TIME (the stock
//                                     scene clones all six at once into six free slots, which 28
//                                     children could not have). The clone goes into a free slot when
//                                     there is one; in a full house (2 parents + 28 children) the
//                                     child's own slot holds the adult clone while it is on show and
//                                     the child is put back byte for byte when the next candidate is
//                                     shown (or before any save). The scene's stock six-entry arrays
//                                     only ever hold the one candidate on show, at index 0, so the
//                                     stock Accept code (StartNextGeneration(clone, source)) is used
//                                     unchanged.
//   theGameState::Save / Load         after a save of a family slot, the sidecar is written (atomic:
//                                     a temp file, then a replace) with a hash of the save file it
//                                     belongs to; the game's own backup of the previous save (slot +
//                                     20) gets the previous sidecar the same way. After a load the
//                                     sidecar whose hash matches the loaded file is used; an
//                                     unreadable or foreign sidecar is moved aside, never overwritten.
//
// The executable also has a small table in its .vf2kidt section (the extra children's slots) that
// B200's own generated code reads to tell a child from a spouse; this DLL keeps it current.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include "b200kids_sites.h"

// ---------------------------------------------------------------- the sites
static unsigned Sites[KIDS_SITE_COUNT];
#define SITE(name) (Sites[KIDS_SITE_##name])

// ---------------------------------------------------------------- status block
// B200Kids_Status: what this launch installed, and what the last load and save did.
//   magic 'B2KC', version, requested, resolved, installed, writeMask, extras (entries held),
//   lastLoad (0 none, 1 exact sidecar, 2 backup sidecar, 3 roster recovery, 4 nothing to use,
//   5 sidecar moved aside), lastSave (0 none, 1 written, 2 nothing to write, 3 write failed)
struct KidsStatus {
    unsigned magic;
    unsigned version;
    unsigned requested;
    unsigned resolved;
    unsigned installed;
    unsigned writeMask;
    unsigned extras;
    unsigned lastLoad;
    unsigned lastSave;
};
extern "C" __declspec(dllexport) volatile KidsStatus B200Kids_Status = { 0x434B3242u, 1u, 0, 0, 0, 0, 0, 0, 0 };

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
// vf2kids.log beside the DLL: what this launch installed, and one line per load and save that used
// or wrote a sidecar. Not in the emulator test build.
static bool LogStarted;

#ifdef B200KIDS_TEST
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
    while (Folder[n] && n + 12 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *name = L"vf2kids.log";
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

static unsigned ExecutableSections(ImageRange *code, unsigned *count) {
    HMODULE exe = GetModuleHandleW(0);
    *count = 0;
    if (!exe) return 0;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)exe;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    const IMAGE_SECTION_HEADER *s = IMAGE_FIRST_SECTION(nt);
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

// The shared table in the executable's .vf2kidt section (writable data). Null unless it is there,
// exactly once, big enough, and carries the magic and version.
struct KidsTable {
    unsigned magic;
    unsigned version;
    int count;
    int slots[KIDS_MAX_EXTRA_CHILDREN];
};

static volatile KidsTable *FindTable() {
    HMODULE exe = GetModuleHandleW(0);
    if (!exe) return 0;
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)exe;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    const IMAGE_SECTION_HEADER *s = IMAGE_FIRST_SECTION(nt);
    volatile KidsTable *found = 0;
    unsigned hits = 0;
    static const char name[8] = { '.', 'v', 'f', '2', 'k', 'i', 'd', 't' };
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        bool same = true;
        for (unsigned k = 0; k < 8; ++k) if (s[i].Name[k] != (unsigned char)name[k]) same = false;
        if (!same) continue;
        ++hits;
        if (s[i].Misc.VirtualSize < sizeof(KidsTable) || !(s[i].Characteristics & IMAGE_SCN_MEM_WRITE)) return 0;
        found = (volatile KidsTable *)((unsigned char *)exe + s[i].VirtualAddress);
    }
    if (hits != 1 || !found) return 0;
    if (found->magic != KIDS_TABLE_MAGIC || found->version != KIDS_TABLE_VERSION) return 0;
    return found;
}

#ifdef B200KIDS_TEST
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

static const unsigned kPinCount = sizeof(KIDS_PINS) / sizeof(KIDS_PINS[0]);
static unsigned PinAt[kPinCount];

static bool Resolve() {
    static ImageRange code[kMaxRanges];
    unsigned codeCount = 0;
    if (!ExecutableSections(code, &codeCount) || !codeCount) return false;
    for (unsigned i = 0; i < kPinCount; ++i) PinAt[i] = 0;
    for (unsigned i = 0; i < kPinCount; ++i) {
        const KidsPin &pin = KIDS_PINS[i];
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
            const KidsPin &pin = KIDS_PINS[i];
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
    for (unsigned i = 0; i < kPinCount; ++i) if (!PinAt[i]) { Log("pin %s never resolved", 0, 0, KIDS_PINS[i].name); return false; }
    bool have[KIDS_SITE_COUNT];
    for (unsigned i = 0; i < KIDS_SITE_COUNT; ++i) have[i] = false;
    for (unsigned e = 0; e < sizeof(KIDS_EVIDENCE) / sizeof(KIDS_EVIDENCE[0]); ++e) {
        const KidsEvidence &ev = KIDS_EVIDENCE[e];
        unsigned at = PinAt[ev.pin] + ev.offset;
        unsigned v = ev.kind == 'L' ? at : *(const unsigned *)at;
        if (have[ev.site] && Sites[ev.site] != v) { Log("site %u: derivations disagree", ev.site); return false; }
        Sites[ev.site] = v;
        have[ev.site] = true;
    }
    for (unsigned i = 0; i < KIDS_SITE_COUNT; ++i) if (!have[i]) { Log("site %u is underived", i); return false; }
    for (unsigned c = 0; c < sizeof(KIDS_CALLS) / sizeof(KIDS_CALLS[0]); ++c) {
        const KidsCall &call = KIDS_CALLS[c];
        unsigned target = 0;
        if (!CallTarget(code, codeCount, PinAt[call.pin] + call.offset, &target)) { Log("call %u is not a call", c); return false; }
        if (call.function >= 0 && target != Sites[call.function]) { Log("call %u targets another function", c); return false; }
    }
    return true;
}

// ================================================================ the game
typedef void *(__thiscall *GetVillagerFn)(void *manager, int slot);
typedef int (__thiscall *FindEmptySlotFn)(void *manager);
typedef int (__thiscall *ClonePeepFn)(void *manager, void *villager);
typedef void (__thiscall *CloneAsAdultFn)(void *dest, void *src);
typedef const char *(__thiscall *MakePathFn)(void *state, int slot);

typedef bool (__thiscall *AddOffspringFn)(void *tree, void *villager);
typedef void (__thiscall *ChangeNameFn)(void *tree, void *villager, const char *name);
typedef int (__thiscall *CountSurvivingFn)(void *tree);
typedef void (__thiscall *ReportDeathFn)(void *tree, void *villager);
typedef void (__thiscall *ResetFn)(void *tree);
typedef bool (__thiscall *StartNextGenerationFn)(void *tree, void *villager, int peep);
typedef void (__thiscall *CreateCandidatesFn)(void *scene);
typedef int (__thiscall *GetNextCandidateFn)(void *scene);
typedef bool (__thiscall *GameStateSlotFn)(void *state, int slot);

// Trampolines (the stock function, entered through its own first instructions).
static AddOffspringFn OrigAddOffspring;
static ChangeNameFn OrigChangeName;
static CountSurvivingFn OrigCountSurviving;
static ReportDeathFn OrigReportDeath;
static ResetFn OrigReset;
static StartNextGenerationFn OrigStartNextGeneration;
static CreateCandidatesFn OrigCreateCandidates;
static GetNextCandidateFn OrigGetNextCandidate;
static GameStateSlotFn OrigSave;
static GameStateSlotFn OrigLoad;

static volatile KidsTable *Table;

static unsigned char *Tree() { return (unsigned char *)SITE(FAMILY_TREE); }
static unsigned char *Manager() { return (unsigned char *)SITE(VILLAGER_MANAGER); }

static unsigned char *Villager(int slot) {
    if (slot < 0 || slot >= (int)KIDS_HOUSEHOLD_SLOTS) return 0;
    return Manager() + KIDS_VILLAGER_ARRAY_OFFSET + (unsigned)slot * KIDS_VILLAGER_STRIDE;
}

static int I32(const unsigned char *p, unsigned off) { return *(const int *)(p + off); }

static int Generations() { return I32(Tree(), 4); }

// The current family record, as CFamilyTree::GetCurrentFamily computes it (null when there is none).
static unsigned char *CurrentFamily() {
    int gen = Generations();
    if (gen <= 0 || gen > (int)KIDS_TREE_GENERATIONS) return 0;
    unsigned char *rec = Tree() + gen * KIDS_FAMILY_RECORD_SIZE - KIDS_FAMILY_RECORD_BASE;
    return rec[0] ? rec : 0;
}

// The stock record's child count (the dword EmptyOffspringSlots and AddOffspring read), 0..6.
static int StockChildren() {
    int gen = Generations();
    if (gen <= 0 || gen > (int)KIDS_TREE_GENERATIONS) return 0;
    int n = I32(Tree(), gen * KIDS_FAMILY_RECORD_SIZE - KIDS_FAMILY_RECORD_BASE + KIDS_RECORD_CHILD_COUNT);
    if (n < 0) n = 0;
    if (n > (int)KIDS_TREE_CHILDREN) n = KIDS_TREE_CHILDREN;
    return n;
}

// theGameState's instance (the pointer theGameState::Get() returns; read, never created here).
static const unsigned char *GameState() { return *(const unsigned char *const *)SITE(GAME_STATE_INSTANCE); }

// ================================================================ the extra children
enum { STATE_ALIVE = 1, STATE_DEAD = 2, STATE_GONE = 3 };
static const unsigned kNameBytes = 28;

struct Extra {
    int slot;
    int gender;
    int state;
    int head;
    int body;
    int age;
    char name[kNameBytes];
    char previous[kNameBytes];   // the name before the last ChangeName (not saved)
};

static Extra Extras[KIDS_MAX_EXTRA_CHILDREN];
static unsigned ExtraCount;

static bool NameEquals(const char *a, const char *b) {
    for (unsigned i = 0; i < KIDS_VILLAGER_NAME_LEN; ++i) {
        if (a[i] != b[i]) return false;
        if (!a[i]) return true;
    }
    return true;
}

static void CopyName(char *dst, const char *src) {
    unsigned i = 0;
    for (; i < KIDS_VILLAGER_NAME_LEN && src[i]; ++i) dst[i] = src[i];
    for (; i < kNameBytes; ++i) dst[i] = 0;
}

// Is the villager in the entry's slot still that child? Slot (the game's own index; a slot never
// moves), gender (never changes) and name (followed through ChangeName).
static bool Matches(const Extra &e) {
    const unsigned char *v = Villager(e.slot);
    if (!v) return false;
    if (I32(v, KIDS_VILLAGER_GENDER) != e.gender) return false;
    const char *name = (const char *)(v + KIDS_VILLAGER_NAME);
    return NameEquals(name, e.name) || (e.previous[0] && NameEquals(name, e.previous));
}

static bool Active(int slot) {
    const unsigned char *v = Villager(slot);
    return v && v[KIDS_VILLAGER_ACTIVE] != 0;
}

static void MirrorTable() {
    B200Kids_Status.extras = ExtraCount;
    if (!Table) return;
    int n = 0;
    for (unsigned i = 0; i < ExtraCount; ++i)
        if (Extras[i].state == STATE_ALIVE) Table->slots[n++] = Extras[i].slot;
    for (int k = n; k < (int)KIDS_MAX_EXTRA_CHILDREN; ++k) Table->slots[k] = -1;
    Table->count = n;
}

// A living entry whose slot now holds someone else is gone (it still counts as born).
static void Sweep() {
    bool changed = false;
    for (unsigned i = 0; i < ExtraCount; ++i) {
        if (Extras[i].state == STATE_ALIVE && !Matches(Extras[i])) {
            Extras[i].state = STATE_GONE;
            changed = true;
        }
    }
    if (changed) MirrorTable();
}

static void ClearExtras() {
    ExtraCount = 0;
    Zero(Extras, sizeof(Extras));
    MirrorTable();
}

// Household slots FindEmptySlot would give out: inactive and not reserved for a baby on the way.
static int FreeSlots() {
    const unsigned char *state = GameState();
    int reserved[3] = { -1, -1, -1 };
    if (state)
        for (int k = 0; k < 3; ++k) reserved[k] = I32(state, KIDS_GAME_STATE_RESERVED_BABY + 4 * k);
    int n = 0;
    for (int slot = 0; slot < (int)KIDS_HOUSEHOLD_SLOTS; ++slot) {
        if (Active(slot)) continue;
        if (slot == reserved[0] || slot == reserved[1] || slot == reserved[2]) continue;
        ++n;
    }
    return n;
}

// ================================================================ hooks: the Family Tree
// CFamilyTree::EmptyOffspringSlots (replaced). Stock: 6 - count (6 with no family).
static int __fastcall EmptyOffspringSlots(void *, void *) {
    Sweep();
    int born = StockChildren() + (int)ExtraCount;
    int room = (int)KIDS_MAX_CHILDREN - born;
    if (room < 0) room = 0;
    int free = FreeSlots();
    return room < free ? room : free;
}

static bool __fastcall AddOffspring(void *tree, void *, void *villager) {
    int gen = Generations();
    if (gen <= 0 || gen > (int)KIDS_TREE_GENERATIONS) return OrigAddOffspring(tree, villager);
    int stock = I32(Tree(), gen * KIDS_FAMILY_RECORD_SIZE - KIDS_FAMILY_RECORD_BASE + KIDS_RECORD_CHILD_COUNT);
    if (stock < (int)KIDS_TREE_CHILDREN) return OrigAddOffspring(tree, villager);
    if (stock > (int)KIDS_TREE_CHILDREN || !villager) return false;
    Sweep();
    if (ExtraCount >= KIDS_MAX_EXTRA_CHILDREN) return false;
    const unsigned char *v = (const unsigned char *)villager;
    int slot = I32(v, KIDS_VILLAGER_SLOT);
    if (slot < 0 || slot >= (int)KIDS_HOUSEHOLD_SLOTS) return false;
    // The slot now holds this child, so an older entry for the same slot is someone else.
    for (unsigned i = 0; i < ExtraCount; ++i)
        if (Extras[i].slot == slot && Extras[i].state == STATE_ALIVE) Extras[i].state = STATE_GONE;
    Extra &e = Extras[ExtraCount++];
    Zero(&e, sizeof(e));
    e.slot = slot;
    e.gender = I32(v, KIDS_VILLAGER_GENDER);
    e.state = STATE_ALIVE;
    e.head = I32(v, KIDS_VILLAGER_HEAD);
    e.body = I32(v, KIDS_VILLAGER_BODY);
    e.age = I32(v, KIDS_VILLAGER_AGE);
    CopyName(e.name, (const char *)(v + KIDS_VILLAGER_NAME));
    MirrorTable();
    return true;
}

static int __fastcall CountSurviving(void *tree, void *) {
    int n = OrigCountSurviving(tree);
    Sweep();
    for (unsigned i = 0; i < ExtraCount; ++i)
        if (Extras[i].state == STATE_ALIVE && Active(Extras[i].slot)) ++n;
    return n;
}

static void __fastcall ReportDeath(void *tree, void *, void *villager) {
    if (villager) {
        int slot = I32((const unsigned char *)villager, KIDS_VILLAGER_SLOT);
        for (unsigned i = 0; i < ExtraCount; ++i) {
            if (Extras[i].state == STATE_ALIVE && Extras[i].slot == slot && Matches(Extras[i])) {
                Extras[i].state = STATE_DEAD;
                MirrorTable();
            }
        }
    }
    OrigReportDeath(tree, villager);
}

static void __fastcall ChangeName(void *tree, void *, void *villager, const char *name) {
    OrigChangeName(tree, villager, name);
    if (!villager || !name) return;
    int slot = I32((const unsigned char *)villager, KIDS_VILLAGER_SLOT);
    for (unsigned i = 0; i < ExtraCount; ++i) {
        Extra &e = Extras[i];
        if (e.state == STATE_ALIVE && e.slot == slot && Matches(e)) {
            Copy(e.previous, e.name, kNameBytes);
            CopyName(e.name, name);
        }
    }
}

// ================================================================ hooks: Next Generation
// The candidate engine, used only while an extra child exists.
struct Engine {
    bool on;
    void *scene;
    int count;
    int cursor;
    int sources[KIDS_MAX_CHILDREN];
    int swapped;           // the child slot whose bytes are in ChildImage (-1: none)
};
static Engine Next = { false, 0, 0, -1, { 0 }, -1 };
static unsigned char ChildImage[KIDS_VILLAGER_STRIDE];
static unsigned char AdultImage[KIDS_VILLAGER_STRIDE];

// Put the child back byte for byte (the adult clone on show was made in its own slot).
static void RestoreSwappedChild() {
    if (Next.swapped < 0) return;
    unsigned char *v = Villager(Next.swapped);
    if (v) Copy(v, ChildImage, KIDS_VILLAGER_STRIDE);
    Next.swapped = -1;
}

static void EndEngine() {
    Next.on = false;
    Next.scene = 0;
    Next.count = 0;
    Next.cursor = -1;
    Next.swapped = -1;
}

static void __fastcall CreateCandidates(void *scene, void *) {
    RestoreSwappedChild();
    Sweep();
    unsigned extras = 0;
    for (unsigned i = 0; i < ExtraCount; ++i)
        if (Extras[i].state == STATE_ALIVE && Matches(Extras[i])) ++extras;
    unsigned char *rec = CurrentFamily();
    if (!extras || !rec) {
        EndEngine();
        OrigCreateCandidates(scene);
        return;
    }
    unsigned char *s = (unsigned char *)scene;
    *(int *)(s + KIDS_ADOPTION_COUNT) = 0;
    *(int *)(s + KIDS_ADOPTION_CURSOR) = -1;
    int n = 0;
    // The stock six first, as the stock scene takes them (every recorded child not dead).
    int stock = StockChildren();
    for (int c = 0; c < stock; ++c) {
        int slot = I32(rec, KIDS_RECORD_CHILDREN + (unsigned)c * KIDS_PEEP_RECORD_SIZE + KIDS_PEEP_SLOT);
        if (slot == -1) continue;
        if (slot < 0 || slot >= (int)KIDS_HOUSEHOLD_SLOTS) continue;
        Next.sources[n++] = slot;
    }
    for (unsigned i = 0; i < ExtraCount && n < (int)KIDS_MAX_CHILDREN; ++i)
        if (Extras[i].state == STATE_ALIVE && Matches(Extras[i])) Next.sources[n++] = Extras[i].slot;
    Next.on = true;
    Next.scene = scene;
    Next.count = n;
    Next.cursor = -1;
    Next.swapped = -1;
    // GetNextCandidate cycles the stock arrays by this count; only index 0 is ever used.
    *(int *)(s + KIDS_ADOPTION_COUNT) = n > 0 ? 1 : 0;
}

// An adult clone of the child in `source`, never into the child's own slot by the stock route.
static int MakeCandidate(int source) {
    unsigned char *child = Villager(source);
    if (!child) return -1;
    int free = ((FindEmptySlotFn)SITE(VM_FIND_EMPTY))(Manager());
    if (free >= 0 && free != source)
        return ((ClonePeepFn)SITE(VM_CLONE_PEEP))(Manager(), child);
    // A full house (or the only free slot is the child's own): the clone is made in the child's
    // slot from a copy of the child, which is put back before anything else is shown or saved.
    Copy(ChildImage, child, KIDS_VILLAGER_STRIDE);
    ((CloneAsAdultFn)SITE(V_CLONE_AS_ADULT))(child, ChildImage);
    Next.swapped = source;
    return source;
}

static int __fastcall GetNextCandidate(void *scene, void *) {
    if (!Next.on || scene != Next.scene || Next.count <= 0) return OrigGetNextCandidate(scene);
    RestoreSwappedChild();
    Next.cursor = Next.cursor + 1;
    if (Next.cursor < 0 || Next.cursor >= Next.count) Next.cursor = 0;
    int source = Next.sources[Next.cursor];
    int clone = MakeCandidate(source);
    unsigned char *s = (unsigned char *)scene;
    *(int *)(s + KIDS_ADOPTION_CLONES) = clone;
    *(int *)(s + KIDS_ADOPTION_SOURCES) = source;   // the child's slot, as the stock scene records it
    *(int *)(s + KIDS_ADOPTION_CURSOR) = 0;
    return clone;
}

static bool __fastcall StartNextGeneration(void *tree, void *, void *villager, int peep) {
    bool started = OrigStartNextGeneration(tree, villager, peep);
    // Accept (or a new family): the clone on show is the heir, so a child's slot that holds it stays
    // as it is; the rest of the household leaves in the stock code that follows.
    EndEngine();
    if (started) ClearExtras();
    return started;
}

static void __fastcall ResetTree(void *tree, void *) {
    OrigReset(tree);
    RestoreSwappedChild();
    EndEngine();
    ClearExtras();
}

// ================================================================ the sidecar
// Little-endian, all fields 32-bit unless said otherwise:
//   0  "VF2KIDS\0"        8  version (1)       12 "VF2B200\0"        20 file size
//   24 save file FNV-1a 64 (8)                 32 save file size
//   36 generations         40 parent 1 slot     44 parent 1 gender    48 entry count (0..22)
//   52 entries, 64 bytes each: slot, gender, state (1 alive, 2 dead, 3 gone), head, body, age,
//      name[28], reserved[12]
//   then the FNV-1a 64 of every byte before it (8).
static const unsigned kHeader = 52;
static const unsigned kEntry = 64;
static const unsigned kMaxFile = kHeader + KIDS_MAX_EXTRA_CHILDREN * kEntry + 8;
static unsigned char FileBuffer[kMaxFile];
static unsigned char ReadBuffer[0x10000];

struct Sidecar {
    unsigned long long saveHash;
    unsigned saveSize;
    int generations;
    int parentSlot;
    int parentGender;
    unsigned count;
    Extra entries[KIDS_MAX_EXTRA_CHILDREN];
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

static bool HashFile(const char *path, unsigned long long *hash, unsigned *size) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return false;
    unsigned long long v = kFnvBasis;
    unsigned total = 0;
    bool ok = true;
    for (;;) {
        DWORD got = 0;
        if (!ReadFile(h, ReadBuffer, sizeof(ReadBuffer), &got, 0)) { ok = false; break; }
        if (!got) break;
        v = Fnv(v, ReadBuffer, got);
        total += got;
    }
    CloseHandle(h);
    *hash = v;
    *size = total;
    return ok;
}

static unsigned Length(const char *s) { unsigned n = 0; while (s[n]) ++n; return n; }

// The sidecar of the save file the game uses for `slot`: <save folder>\Virtual Families 2 Patcher
// Data\Children\<save file name>.dat. `folder` (optional) receives the Children folder.
static bool SidecarPath(void *state, int slot, char *out, unsigned cap, char *saveOut, char *folder) {
    if (!state) return false;
    void **vtable = *(void ***)state;
    const char *save = ((MakePathFn)vtable[KIDS_LDW_PATH_VSLOT / 4])(state, slot);
    if (!save) return false;
    unsigned n = Length(save);
    if (n == 0 || n + 1 >= MAX_PATH) return false;
    if (saveOut) Copy(saveOut, save, n + 1);
    unsigned cut = n;
    while (cut > 0 && save[cut - 1] != '\\' && save[cut - 1] != '/') --cut;
    if (cut == 0 || cut == n) return false;
    static const char middle[] = "Virtual Families 2 Patcher Data\\Children\\";
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

static void EnsureFolders(const char *children) {
    char path[MAX_PATH];
    unsigned n = Length(children);
    if (n + 1 >= MAX_PATH) return;
    Copy(path, children, n + 1);
    unsigned cut = n;
    while (cut > 0 && path[cut - 1] != '\\') --cut;
    if (cut > 1) {
        path[cut - 1] = 0;
        CreateDirectoryA(path, 0);       // the Patcher Data folder (an existing one is fine)
        path[cut - 1] = '\\';
    }
    CreateDirectoryA(path, 0);
}

// 1 = read and valid, 0 = no file, -1 = there but unreadable or foreign.
static int ReadSidecar(const char *path, Sidecar *out) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return GetLastError() == ERROR_FILE_NOT_FOUND || GetLastError() == ERROR_PATH_NOT_FOUND ? 0 : -1;
    DWORD got = 0;
    BOOL ok = ReadFile(h, FileBuffer, kMaxFile, &got, 0);
    DWORD more = 0;
    unsigned char extra[1];
    if (ok && got == kMaxFile) ReadFile(h, extra, 1, &more, 0);
    CloseHandle(h);
    if (!ok || more) return -1;
    static const unsigned char magic[8] = { 'V', 'F', '2', 'K', 'I', 'D', 'S', 0 };
    static const unsigned char tag[8] = { 'V', 'F', '2', 'B', '2', '0', '0', 0 };
    if (got < kHeader + 8) return -1;
    for (unsigned k = 0; k < 8; ++k) if (FileBuffer[k] != magic[k] || FileBuffer[12 + k] != tag[k]) return -1;
    if (Get32(FileBuffer + 8) != KIDS_SIDECAR_VERSION || Get32(FileBuffer + 20) != got) return -1;
    unsigned count = Get32(FileBuffer + 48);
    if (count > KIDS_MAX_EXTRA_CHILDREN || got != kHeader + count * kEntry + 8) return -1;
    unsigned long long sum = Fnv(kFnvBasis, FileBuffer, got - 8);
    if (Get32(FileBuffer + got - 8) != (unsigned)sum || Get32(FileBuffer + got - 4) != (unsigned)(sum >> 32)) return -1;
    out->saveHash = Get32(FileBuffer + 24) | ((unsigned long long)Get32(FileBuffer + 28) << 32);
    out->saveSize = Get32(FileBuffer + 32);
    out->generations = (int)Get32(FileBuffer + 36);
    out->parentSlot = (int)Get32(FileBuffer + 40);
    out->parentGender = (int)Get32(FileBuffer + 44);
    out->count = count;
    for (unsigned i = 0; i < count; ++i) {
        const unsigned char *p = FileBuffer + kHeader + i * kEntry;
        Extra &e = out->entries[i];
        Zero(&e, sizeof(e));
        e.slot = (int)Get32(p);
        e.gender = (int)Get32(p + 4);
        e.state = (int)Get32(p + 8);
        e.head = (int)Get32(p + 12);
        e.body = (int)Get32(p + 16);
        e.age = (int)Get32(p + 20);
        for (unsigned k = 0; k < kNameBytes; ++k) e.name[k] = (char)p[24 + k];
        e.name[kNameBytes - 1] = 0;
        if (e.slot < 0 || e.slot >= (int)KIDS_HOUSEHOLD_SLOTS || e.state < STATE_ALIVE || e.state > STATE_GONE)
            return -1;
    }
    return 1;
}

static bool WriteSidecar(const char *path, const char *folder, unsigned long long saveHash, unsigned saveSize) {
    unsigned char *rec = CurrentFamily();
    unsigned size = kHeader + ExtraCount * kEntry + 8;
    Zero(FileBuffer, size);
    Copy(FileBuffer, "VF2KIDS\0", 8);
    Put32(FileBuffer + 8, KIDS_SIDECAR_VERSION);
    Copy(FileBuffer + 12, "VF2B200\0", 8);
    Put32(FileBuffer + 20, size);
    Put32(FileBuffer + 24, (unsigned)saveHash);
    Put32(FileBuffer + 28, (unsigned)(saveHash >> 32));
    Put32(FileBuffer + 32, saveSize);
    Put32(FileBuffer + 36, (unsigned)Generations());
    Put32(FileBuffer + 40, rec ? (unsigned)I32(rec, KIDS_RECORD_PARENT1 + KIDS_PEEP_SLOT) : 0xFFFFFFFFu);
    Put32(FileBuffer + 44, rec ? (unsigned)I32(rec, KIDS_RECORD_PARENT1 + KIDS_PEEP_GENDER) : 0xFFFFFFFFu);
    Put32(FileBuffer + 48, ExtraCount);
    for (unsigned i = 0; i < ExtraCount; ++i) {
        unsigned char *p = FileBuffer + kHeader + i * kEntry;
        const Extra &e = Extras[i];
        Put32(p, (unsigned)e.slot);
        Put32(p + 4, (unsigned)e.gender);
        Put32(p + 8, (unsigned)e.state);
        Put32(p + 12, (unsigned)e.head);
        Put32(p + 16, (unsigned)e.body);
        Put32(p + 20, (unsigned)e.age);
        Copy(p + 24, e.name, kNameBytes);
    }
    unsigned long long sum = Fnv(kFnvBasis, FileBuffer, size - 8);
    Put32(FileBuffer + size - 8, (unsigned)sum);
    Put32(FileBuffer + size - 4, (unsigned)(sum >> 32));
    EnsureFolders(folder);
    char temp[MAX_PATH + 8];
    unsigned n = Length(path);
    Copy(temp, path, n);
    Copy(temp + n, ".tmp", 5);
    HANDLE h = CreateFileA(temp, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    BOOL ok = WriteFile(h, FileBuffer, size, &written, 0) && written == size;
    if (ok) ok = FlushFileBuffers(h);
    CloseHandle(h);
    if (!ok) { DeleteFileA(temp); return false; }
    if (!MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) { DeleteFileA(temp); return false; }
    return true;
}

// An unreadable or foreign sidecar is kept, renamed beside itself: "<name>.unreadable-N.dat".
static void MoveAside(const char *path) {
    char aside[MAX_PATH + 24];
    unsigned n = Length(path);
    if (n < 4 || n + 20 >= sizeof(aside)) return;
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
        if (MoveFileExA(path, aside, 0)) return;
        if (GetLastError() != ERROR_ALREADY_EXISTS && GetLastError() != ERROR_FILE_EXISTS) return;
    }
}

static bool SameFamily(const Sidecar &file) {
    unsigned char *rec = CurrentFamily();
    if (!rec) return false;
    return file.generations == Generations()
        && file.parentSlot == I32(rec, KIDS_RECORD_PARENT1 + KIDS_PEEP_SLOT)
        && file.parentGender == I32(rec, KIDS_RECORD_PARENT1 + KIDS_PEEP_GENDER);
}

// exact: the sidecar was written with this very save file, so its dead and gone entries (which count
// toward the 28) are kept; otherwise only the children still found in their slots are kept.
static void Adopt(const Sidecar &file, bool exact) {
    ClearExtras();
    if (StockChildren() < (int)KIDS_TREE_CHILDREN) return;   // extras exist only after the stock six
    for (unsigned i = 0; i < file.count && ExtraCount < KIDS_MAX_EXTRA_CHILDREN; ++i) {
        Extra e = file.entries[i];
        bool found = Matches(e);
        if (e.state == STATE_ALIVE && !found) {
            if (!exact) continue;
            e.state = STATE_GONE;
        }
        if (!exact && e.state != STATE_ALIVE) continue;
        Extras[ExtraCount++] = e;
    }
    MirrorTable();
}

static void AfterLoad(void *state, int slot) {
    char path[MAX_PATH + 64], save[MAX_PATH], folder[MAX_PATH + 64];
    char backup[MAX_PATH + 64], backupSave[MAX_PATH];
    if (!SidecarPath(state, slot, path, sizeof(path), save, folder)) return;
    unsigned long long hash = 0;
    unsigned size = 0;
    bool hashed = HashFile(save, &hash, &size);
    int r = ReadSidecar(path, &Loaded);
    B200Kids_Status.lastLoad = 4;
    if (r < 0) {
        MoveAside(path);
        B200Kids_Status.lastLoad = 5;
        Log("slot %u: an unreadable sidecar was moved aside", (unsigned)slot);
        r = 0;
    }
    if (r == 1 && hashed && Loaded.saveHash == hash && Loaded.saveSize == size && SameFamily(Loaded)) {
        Adopt(Loaded, true);
        B200Kids_Status.lastLoad = 1;
        Log("slot %u: %u extra children from the sidecar", (unsigned)slot, ExtraCount);
        return;
    }
    // The game's own backup (slot + 20) is the previous save: a restored backup has its sidecar there.
    static Sidecar backupFile;
    if (hashed && SidecarPath(state, slot + (int)KIDS_SAVE_BACKUP_OFFSET, backup, sizeof(backup), backupSave, 0)
        && ReadSidecar(backup, &backupFile) == 1 && backupFile.saveHash == hash && backupFile.saveSize == size
        && SameFamily(backupFile)) {
        Adopt(backupFile, true);
        B200Kids_Status.lastLoad = 2;
        Log("slot %u: %u extra children from the backup's sidecar", (unsigned)slot, ExtraCount);
        return;
    }
    if (r == 1 && SameFamily(Loaded)) {
        Adopt(Loaded, false);
        B200Kids_Status.lastLoad = 3;
        Log("slot %u: the sidecar is for another save of this family; kept the %u children still at home",
            (unsigned)slot, ExtraCount);
    }
}

static bool __fastcall GameStateLoad(void *state, void *, int slot) {
    RestoreSwappedChild();
    bool loaded = OrigLoad(state, slot);
    if (loaded && slot > 0) AfterLoad(state, slot);
    return loaded;
}

static bool __fastcall GameStateSave(void *state, void *, int slot) {
    if (slot <= 0) return OrigSave(state, slot);
    Sweep();
    char path[MAX_PATH + 64], save[MAX_PATH], folder[MAX_PATH + 64];
    char backup[MAX_PATH + 64];
    bool named = SidecarPath(state, slot, path, sizeof(path), save, folder)
        && SidecarPath(state, slot + (int)KIDS_SAVE_BACKUP_OFFSET, backup, sizeof(backup), 0, 0);
    if (named) {
        // ldwGameState::Save removes the save at slot + 20 and renames this slot's save to it.
        DeleteFileA(backup);
        MoveFileExA(path, backup, 0);
    }
    // The adult on show in a child's own slot is not saved: the child is.
    bool swapped = Next.swapped >= 0;
    unsigned char *v = swapped ? Villager(Next.swapped) : 0;
    if (v) {
        Copy(AdultImage, v, KIDS_VILLAGER_STRIDE);
        Copy(v, ChildImage, KIDS_VILLAGER_STRIDE);
    }
    bool saved = OrigSave(state, slot);
    if (v) Copy(v, AdultImage, KIDS_VILLAGER_STRIDE);
    if (!saved || !named) return saved;
    if (!ExtraCount) { B200Kids_Status.lastSave = 2; return saved; }
    unsigned long long hash = 0;
    unsigned size = 0;
    if (HashFile(save, &hash, &size) && WriteSidecar(path, folder, hash, size)) {
        B200Kids_Status.lastSave = 1;
    } else {
        B200Kids_Status.lastSave = 3;
        Log("slot %u: the sidecar could not be written", (unsigned)slot);
    }
    return saved;
}

// ================================================================ plan and install
static const unsigned kMaxWrites = 16;

struct HookWrite {
    unsigned va;
    unsigned char bytes[5];
    unsigned char original[5];
};

struct Plan {
    HookWrite writes[kMaxWrites];
    unsigned count;
    bool ok;
};

// Trampolines: the stolen instructions, then a jmp back. In a page of this DLL's own data that is
// made executable for them.
__declspec(align(4096)) static unsigned char Trampolines[4096];
static unsigned TrampolineUsed;

static void *Handler(unsigned site) {
    switch (site) {
    case KIDS_SITE_FT_ADD_OFFSPRING: return (void *)&AddOffspring;
    case KIDS_SITE_FT_CHANGE_NAME: return (void *)&ChangeName;
    case KIDS_SITE_FT_COUNT_SURVIVING: return (void *)&CountSurviving;
    case KIDS_SITE_FT_EMPTY_OFFSPRING: return (void *)&EmptyOffspringSlots;
    case KIDS_SITE_FT_REPORT_DEATH: return (void *)&ReportDeath;
    case KIDS_SITE_FT_RESET: return (void *)&ResetTree;
    case KIDS_SITE_FT_START_NEXT_GEN: return (void *)&StartNextGeneration;
    case KIDS_SITE_AD_CREATE_CANDIDATES: return (void *)&CreateCandidates;
    case KIDS_SITE_AD_GET_NEXT: return (void *)&GetNextCandidate;
    case KIDS_SITE_GS_SAVE: return (void *)&GameStateSave;
    case KIDS_SITE_GS_LOAD: return (void *)&GameStateLoad;
    }
    return 0;
}

static void SetOriginal(unsigned site, void *trampoline) {
    switch (site) {
    case KIDS_SITE_FT_ADD_OFFSPRING: OrigAddOffspring = (AddOffspringFn)trampoline; break;
    case KIDS_SITE_FT_CHANGE_NAME: OrigChangeName = (ChangeNameFn)trampoline; break;
    case KIDS_SITE_FT_COUNT_SURVIVING: OrigCountSurviving = (CountSurvivingFn)trampoline; break;
    case KIDS_SITE_FT_REPORT_DEATH: OrigReportDeath = (ReportDeathFn)trampoline; break;
    case KIDS_SITE_FT_RESET: OrigReset = (ResetFn)trampoline; break;
    case KIDS_SITE_FT_START_NEXT_GEN: OrigStartNextGeneration = (StartNextGenerationFn)trampoline; break;
    case KIDS_SITE_AD_CREATE_CANDIDATES: OrigCreateCandidates = (CreateCandidatesFn)trampoline; break;
    case KIDS_SITE_AD_GET_NEXT: OrigGetNextCandidate = (GetNextCandidateFn)trampoline; break;
    case KIDS_SITE_GS_SAVE: OrigSave = (GameStateSlotFn)trampoline; break;
    case KIDS_SITE_GS_LOAD: OrigLoad = (GameStateSlotFn)trampoline; break;
    }
}

static unsigned PinOfSite(unsigned site) {
    for (unsigned e = 0; e < sizeof(KIDS_EVIDENCE) / sizeof(KIDS_EVIDENCE[0]); ++e)
        if (KIDS_EVIDENCE[e].site == site && KIDS_EVIDENCE[e].kind == 'L' && KIDS_EVIDENCE[e].offset == 0)
            return KIDS_EVIDENCE[e].pin;
    return 0xFFFFFFFFu;
}

// Builds every write and every trampoline (the trampolines are this DLL's memory; nothing of the
// game is written here).
static bool PlanHooks(Plan &plan) {
    plan.count = 0;
    plan.ok = true;
    TrampolineUsed = 0;
    for (unsigned h = 0; h < sizeof(KIDS_HOOKS) / sizeof(KIDS_HOOKS[0]); ++h) {
        const KidsHook &hook = KIDS_HOOKS[h];
        unsigned entry = Sites[hook.site];
        unsigned pin = PinOfSite(hook.site);
        void *handler = Handler(hook.site);
        if (pin >= kPinCount || !handler || hook.steal < 5 || hook.steal > 16 || plan.count >= kMaxWrites) return false;
        // The stolen bytes are whole, position-independent instructions with no wildcard (the prover
        // checks it); they must still be exactly the pinned bytes in the live image.
        for (unsigned k = 0; k < hook.steal; ++k)
            if (KIDS_PINS[pin].mask[k] || ((const unsigned char *)entry)[k] != KIDS_PINS[pin].bytes[k]) return false;
        if (!hook.replace) {
            if (TrampolineUsed + hook.steal + 5 + 3 > sizeof(Trampolines)) return false;
            unsigned char *t = Trampolines + TrampolineUsed;
            Copy(t, (const void *)entry, hook.steal);
            t[hook.steal] = 0xE9;
            *(int *)(t + hook.steal + 1) = (int)((entry + hook.steal) - ((unsigned)t + hook.steal + 5));
            SetOriginal(hook.site, t);
            TrampolineUsed += (hook.steal + 5 + 15) & ~15u;
        }
        HookWrite &w = plan.writes[plan.count++];
        w.va = entry;
        w.bytes[0] = 0xE9;
        *(int *)(w.bytes + 1) = (int)((unsigned)handler - (entry + 5));
    }
    return true;
}

// 0 = setting off (nothing planned); -1 = could not be proved (nothing planned); 1 = planned.
static int BuildPlan(bool enabled, Plan &plan) {
    plan.count = 0;
    plan.ok = true;
    if (!enabled) return 0;
    if (!Resolve()) return -1;
    Table = FindTable();
    if (!Table) { Log("the executable has no .vf2kidt table"); return -1; }
    if (!PlanHooks(plan)) return -1;
    return 1;
}

static bool WriteCode(unsigned va, const unsigned char *bytes, unsigned len) {
    DWORD old = 0;
    if (!VirtualProtect((void *)va, len, PAGE_EXECUTE_READWRITE, &old)) return false;
    for (unsigned i = 0; i < len; ++i) ((volatile unsigned char *)va)[i] = bytes[i];
    DWORD ignored = 0;
    BOOL restored = VirtualProtect((void *)va, len, old, &ignored);
    FlushInstructionCache(GetCurrentProcess(), (void *)va, len);
    return restored != FALSE;
}

// All or nothing.
static bool Apply(Plan &plan) {
    DWORD old = 0;
    if (!VirtualProtect(Trampolines, sizeof(Trampolines), PAGE_EXECUTE_READWRITE, &old)) return false;
    for (unsigned i = 0; i < plan.count; ++i) {
        HookWrite &w = plan.writes[i];
        for (unsigned j = 0; j < 5; ++j) w.original[j] = ((const unsigned char *)w.va)[j];
        if (!WriteCode(w.va, w.bytes, 5)) {
            Log("write %u failed; restoring the earlier writes", i);
            for (unsigned j = 0; j < i; ++j) WriteCode(plan.writes[j].va, plan.writes[j].original, 5);
            B200Kids_Status.writeMask = 0;
            return false;
        }
        B200Kids_Status.writeMask |= 1u << i;
    }
    return true;
}

static bool SettingOn() {
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    while (Folder[n] && n + 12 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *name = L"vf2kids.ini";
    for (unsigned i = 0; name[i]; ++i) path[n++] = name[i];
    path[n] = 0;
    return GetPrivateProfileIntW(L"Patches", L"UpTo28Children", 0, path) == 1;
}

// Called once by the executable's loader, before the game loop starts.
extern "C" __declspec(dllexport) void __cdecl B200Kids_Startup() {
    static bool started = false;
    if (started) return;
    started = true;
    DWORD n = GetModuleFileNameW(ThisModule, Folder, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    unsigned cut = n;
    while (cut > 0 && Folder[cut - 1] != L'\\') --cut;
    if (!cut) return;
    Folder[cut] = 0;
    Log("vf2kids_b200 started");
    bool on = SettingOn();
    B200Kids_Status.requested = on ? 1u : 0u;
    static Plan plan;
    int built = BuildPlan(on, plan);
    if (built == 0) { Log("Up to 28 Children is off: the game is stock"); return; }
    if (built < 0) { Log("the executable could not be proved: installing nothing"); return; }
    B200Kids_Status.resolved = 1;
    ClearExtras();
    if (Apply(plan)) {
        B200Kids_Status.installed = 1;
        Log("Up to 28 Children installed (%u writes)", plan.count);
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
#ifdef B200KIDS_TEST
extern "C" __declspec(dllexport) unsigned __cdecl B200Kids_TestScanAddress() { return (unsigned)&ScanPattern; }
extern "C" __declspec(dllexport) void __cdecl B200Kids_TestSetModule(unsigned module) { ThisModule = (HMODULE)module; }
extern "C" __declspec(dllexport) void __cdecl B200Kids_TestSites(unsigned *out) {
    for (unsigned i = 0; i < KIDS_SITE_COUNT; ++i) out[i] = Sites[i];
}
// Plans without writing. out: [status, count, then per write: va, bytes0..3, byte4].
extern "C" __declspec(dllexport) int __cdecl B200Kids_TestPlan(int enabled, unsigned *out) {
    static Plan plan;
    int built = BuildPlan(enabled != 0, plan);
    out[0] = (unsigned)built;
    out[1] = built > 0 ? plan.count : 0;
    for (unsigned i = 0; built > 0 && i < plan.count; ++i) {
        out[2 + i * 3 + 0] = plan.writes[i].va;
        out[2 + i * 3 + 1] = *(unsigned *)plan.writes[i].bytes;
        out[2 + i * 3 + 2] = plan.writes[i].bytes[4];
    }
    return built;
}
// The extra children: out[0] = count, then per entry slot, gender, state.
extern "C" __declspec(dllexport) void __cdecl B200Kids_TestExtras(int *out) {
    out[0] = (int)ExtraCount;
    for (unsigned i = 0; i < ExtraCount; ++i) {
        out[1 + i * 3] = Extras[i].slot;
        out[2 + i * 3] = Extras[i].gender;
        out[3 + i * 3] = Extras[i].state;
    }
}
// The candidate engine: on, count, cursor, swapped, then the sources.
extern "C" __declspec(dllexport) void __cdecl B200Kids_TestEngine(int *out) {
    out[0] = Next.on ? 1 : 0;
    out[1] = Next.count;
    out[2] = Next.cursor;
    out[3] = Next.swapped;
    for (int i = 0; i < Next.count; ++i) out[4 + i] = Next.sources[i];
}
#endif
