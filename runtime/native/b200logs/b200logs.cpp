// vf2logs_b200.dll -- "Family Logs", the companion DLL for the B200 Virtual Families 2 executable. One
// feature, one DLL: nothing else is installed here.
//
// It is the Virtual Families 1 Family Logs DLL (vf1logs.dll) ported to Virtual Families 2: the Virtual
// Villagers Fun Patcher's logs, in the same files, folders, headers and line formats, for a family.
// Virtual Families 2 keeps no history (docs/vf2-save-format.md section 9: the save holds state, the
// life-event queue is not saved), so every log is written by this DLL at the moment the event happens,
// from the game's own memory, with the game's own words where the game has them (theStringManager:
// "Male", "Female", "Nursing", the causes of death, "New Generation", "{name} is going to college!",
// "%s has been sent away to school!", "Boarding School", "Adoption Services", "The Little Visitor",
// "The Talent Scout"). Per save slot, beside the save:
//
//   <save folder>\Virtual Families 2 Patcher\Save <N>\Logs\
//       Family History\Family History <k>.txt                                 every event, one line each
//       Births and Conceptions\Virtual Families 2 Births and Conceptions Log <k>.txt
//       Deaths\Virtual Families 2 Deaths Log <k>.txt                          with the cause
//       Events\Virtual Families 2 Events Log <k>.txt                          Evict Family, Boarding School,
//                                                                             Adoption Services, The Little
//                                                                             Visitor, The Talent Scout
//       Family Population\Family Population - Save <N>.txt                    the household at each save
//       Family Statistics\Family Statistics - Save <N>.txt                    counts at each save
//   <save folder>\Virtual Families 2 Patcher\Save <N>\Data\
//       Parents\Virtual Families 2 Parents - Save <N>.dat                     each baby's mother and father,
//                                                                             written at conception
//       Log Checks\Virtual Families 2 Backfill - Save <N>.dat                 the once-only backfill marker
//
// Only the data the logs need is kept: a baby's father is known at conception and not at birth (the
// game records the literal "Joey" as every baby's father's name), so the Parents file carries it to the
// birth; the backfill marker says the past was written once (and how many deaths the Family Tree held
// then, for the Deaths count). Babies Born and Oldest Family Member Ever are the game's own statistics.
// Each death is logged once without a file: both ReportDeath callers deactivate the villager right
// after reporting it, so the game reports every death once, also across a save and a load.
//
// Append-only logs are never rewritten; each rolls into a new numbered file (256 numbered records, or
// 2000 history lines). A new family (the adoption of a founder, unless it follows Evict Family) and
// Start Over wipe that slot's folder, Backups excepted; an existing family seen for the first time gets
// its past generations from the save's Family Tree, marked "backfilled, no date", once.
//
// The B200 executable is RELOCATED (DYNAMICBASE) and each of the 32 matrix variants links to different
// addresses, so this DLL holds NO game address. b200logs_sites.h (generated and proved by
// runtime/tools/gen_b200_logs_sites.py) holds pinned runs of the core variant with wildcards where a
// relocated field, a call displacement or another companion's entry hook sits; Resolve() finds every
// run in the live image exactly once and derives each address from where they were found.
//
// The executable's dormant loader (.vf2logs byte, 0 as built) loads this DLL only when the patcher
// setting is on, after the Time Controls and Up to 28 Children DLLs, and calls B200Logs_Startup() once
// before the game loop. Installing is: setting -> resolve -> plan -> apply, all or nothing. With the
// setting off, or anything the resolver cannot prove, NOTHING is written and the game is B200's own
// bytes. What it writes: 14 call retargets (each call goes to a handler here that makes the same call),
// one entry jmp (CVillager::Impregnate, 6 bytes stolen into a trampoline), and theGameState's Save and
// Load vtable slots (chained to whatever they hold: the stock functions or the Time Controls handlers).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include "b200logs_sites.h"

// ---------------------------------------------------------------- the sites
static unsigned Sites[LOGS_SITE_COUNT];
#define SITE(name) (Sites[LOGS_SITE_##name])

// ---------------------------------------------------------------- status block
// B200Logs_Status: what this launch installed and what the logs did.
//   magic 'B2LG', version, requested, resolved, installed, writeMask (bit w: write w live),
//   records (records and lines written this session), lastLoad (0 none, 1 logs created / found,
//   2 backfilled), lastSave (0 none, 1 snapshots written, 2 not written: no folder), wipes.
struct LogsStatus {
    unsigned magic;
    unsigned version;
    unsigned requested;
    unsigned resolved;
    unsigned installed;
    unsigned writeMask;
    unsigned records;
    unsigned lastLoad;
    unsigned lastSave;
    unsigned wipes;
};
extern "C" __declspec(dllexport) volatile LogsStatus B200Logs_Status = { LOGS_STATUS_MAGIC, 1u, 0, 0, 0, 0, 0, 0, 0, 0 };

static HMODULE ThisModule;
static wchar_t Folder[MAX_PATH];

// ================================================================ small helpers (no C runtime)
static void Copy(void *dst, const void *src, unsigned n) {
    volatile unsigned char *d = (volatile unsigned char *)dst;
    const volatile unsigned char *s = (const volatile unsigned char *)src;
    for (unsigned i = 0; i < n; ++i) d[i] = s[i];
}

static void Zero(void *dst, unsigned n) {
    volatile unsigned char *d = (volatile unsigned char *)dst;
    for (unsigned i = 0; i < n; ++i) d[i] = 0;
}

static unsigned Length(const char *s) { unsigned n = 0; while (s && s[n]) ++n; return n; }

static bool SameText(const char *a, const char *b, unsigned max) {
    for (unsigned i = 0; i < max; ++i) {
        if (a[i] != b[i]) return false;
        if (!a[i]) return true;
    }
    return true;
}

static bool StartsWith(const char *s, const char *prefix) {
    for (unsigned i = 0; prefix[i]; ++i) if (s[i] != prefix[i]) return false;
    return true;
}

static char Lower(char c) { return c >= 'A' && c <= 'Z' ? (char)(c - 'A' + 'a') : c; }

static bool SameNameIgnoringCase(const char *a, const char *b) {
    for (unsigned i = 0;; ++i) {
        if (Lower(a[i]) != Lower(b[i])) return false;
        if (!a[i]) return true;
    }
}

// A text being built in a fixed buffer; anything past the end is dropped, never overrun.
struct Text {
    char *buf;
    unsigned cap;
    unsigned n;
    void Init(char *b, unsigned c) { buf = b; cap = c; n = 0; buf[0] = 0; }
    Text &S(const char *s) {
        while (s && *s && n + 1 < cap) buf[n++] = *s++;
        buf[n] = 0;
        return *this;
    }
    Text &Name(const char *s, unsigned max) {   // a game name field: at most `max` bytes, tabs and line ends dropped
        for (unsigned i = 0; s && i < max && s[i] && n + 1 < cap; ++i)
            if (s[i] != '\t' && s[i] != '\r' && s[i] != '\n') buf[n++] = s[i];
        buf[n] = 0;
        return *this;
    }
    Text &U(unsigned v) {
        char d[12];
        unsigned k = 0;
        do { d[k++] = (char)('0' + v % 10); v /= 10; } while (v && k < 11);
        while (k && n + 1 < cap) buf[n++] = d[--k];
        buf[n] = 0;
        return *this;
    }
    Text &I(int v) {
        if (v < 0) { S("-"); return U(0u - (unsigned)v); }
        return U((unsigned)v);
    }
    Text &Two(unsigned v) { if (v < 10) S("0"); return U(v); }
    Text &NL() { return S("\r\n"); }
};

// ---------------------------------------------------------------- install log
// vf2logs.log beside the DLL: what this launch installed. Not in the emulator test build.
static bool LogStarted;

#ifdef B200LOGS_TEST
static void Log(const char *, const char * = 0) {}
#else
static void Log(const char *what, const char *name = 0) {
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    while (Folder[n] && n + 12 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *file = L"vf2logs.log";
    for (unsigned i = 0; file[i]; ++i) path[n++] = file[i];
    path[n] = 0;
    char line[300];
    Text t;
    t.Init(line, sizeof(line));
    t.S(what);
    if (name) t.S(": ").S(name);
    t.NL();
    HANDLE h = CreateFileW(path, LogStarted ? FILE_APPEND_DATA : GENERIC_WRITE, FILE_SHARE_READ, 0,
                           LogStarted ? OPEN_ALWAYS : CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return;
    LogStarted = true;
    DWORD written = 0;
    WriteFile(h, line, t.n, &written, 0);
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

#ifdef B200LOGS_TEST
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

static const unsigned kPinCount = sizeof(LOGS_PINS) / sizeof(LOGS_PINS[0]);
static unsigned PinAt[kPinCount];

static bool Resolve() {
    static ImageRange code[kMaxRanges];
    unsigned codeCount = 0;
    if (!ExecutableSections(code, &codeCount) || !codeCount) return false;
    for (unsigned i = 0; i < kPinCount; ++i) PinAt[i] = 0;
    for (unsigned i = 0; i < kPinCount; ++i) {
        const LogsPin &pin = LOGS_PINS[i];
        if (pin.parent >= 0) continue;
        unsigned hits = 0, at = 0;
        for (unsigned r = 0; r < codeCount && hits < 2; ++r) {
            unsigned h = 0;
            unsigned found = ScanPattern((const unsigned char *)code[r].base, code[r].size, pin.bytes, pin.mask,
                                         pin.len, &h);
            if (h) { if (!hits) at = found; hits += h; }
        }
        if (hits != 1) { Log("a pin was not found exactly once", pin.name); return false; }
        PinAt[i] = at;
    }
    for (unsigned pass = 0; pass < kPinCount; ++pass) {
        for (unsigned i = 0; i < kPinCount; ++i) {
            const LogsPin &pin = LOGS_PINS[i];
            if (pin.parent < 0 || PinAt[i] || !PinAt[pin.parent]) continue;
            unsigned target = 0;
            if (!CallTarget(code, codeCount, PinAt[pin.parent] + pin.call_offset, &target)) {
                Log("a pin's parent has no call there", pin.name);
                return false;
            }
            if (!Inside(code, codeCount, target, pin.len)) { Log("a pin lies outside the code", pin.name); return false; }
            for (unsigned k = 0; k < pin.len; ++k) {
                if (!pin.mask[k] && ((const unsigned char *)target)[k] != pin.bytes[k]) {
                    Log("a call target's bytes differ", pin.name);
                    return false;
                }
            }
            PinAt[i] = target;
        }
    }
    for (unsigned i = 0; i < kPinCount; ++i) if (!PinAt[i]) { Log("a pin never resolved", LOGS_PINS[i].name); return false; }
    bool have[LOGS_SITE_COUNT];
    for (unsigned i = 0; i < LOGS_SITE_COUNT; ++i) have[i] = false;
    for (unsigned e = 0; e < sizeof(LOGS_EVIDENCE) / sizeof(LOGS_EVIDENCE[0]); ++e) {
        const LogsEvidence &ev = LOGS_EVIDENCE[e];
        unsigned at = PinAt[ev.pin] + ev.offset;
        unsigned v = ev.kind == 'L' ? at : *(const unsigned *)at;
        if (have[ev.site] && Sites[ev.site] != v) { Log("two derivations of a site disagree"); return false; }
        Sites[ev.site] = v;
        have[ev.site] = true;
    }
    for (unsigned i = 0; i < LOGS_SITE_COUNT; ++i) if (!have[i]) { Log("a site is underived"); return false; }
    for (unsigned c = 0; c < sizeof(LOGS_CALLS) / sizeof(LOGS_CALLS[0]); ++c) {
        const LogsCall &call = LOGS_CALLS[c];
        unsigned target = 0;
        if (!CallTarget(code, codeCount, PinAt[call.pin] + call.offset, &target)) { Log("a call is not a call"); return false; }
        if (target != Sites[call.function]) { Log("a call targets another function"); return false; }
    }
    unsigned phys = SITE(VM_PHYSIOLOGY);
    if (!(SITE(VM_BIRTH) > phys && SITE(VM_BIRTH) < phys + LOGS_PHYSIOLOGY_SPAN) ||
        !(SITE(VM_BIRTH_END) > phys && SITE(VM_BIRTH_END) < phys + LOGS_PHYSIOLOGY_SPAN)) {
        Log("the delivery is not inside the physiology pass");
        return false;
    }
    return true;
}

// ================================================================ the game
typedef bool (__thiscall *ImpregnateFn)(void *mother, int one, const char *father, int head, int body, int flag);
typedef void (__thiscall *ThisVoidFn)(void *self);
typedef void (__thiscall *TreeVillagerFn)(void *tree, void *villager);
typedef bool (__thiscall *TreeVillagerBoolFn)(void *tree, void *villager);
typedef bool (__thiscall *UpdateParentsFn)(void *tree, void *a, void *b);
typedef bool (__thiscall *NextGenerationFn)(void *tree, void *villager, int source);
typedef bool (__thiscall *GameStateSlotFn)(void *state, int slot);
typedef const char *(__thiscall *MakePathFn)(void *state, int slot);
typedef const char *(__stdcall *GetStringFn)(int id);
typedef void *(__cdecl *SingletonFn)();

static ImpregnateFn OrigImpregnate;
static ThisVoidFn NextPhysiology;
static TreeVillagerFn NextDeathTimeflow, NextDeathBehavior;
static ThisVoidFn NextCollege, NextBoardingSchool, NextTalentScout;
static UpdateParentsFn NextMarriage;
static TreeVillagerBoolFn NextNewFamily, NextLittleVisitor1, NextLittleVisitor2, NextAdoption;
static NextGenerationFn NextNextGeneration;
static ThisVoidFn NextEvict, NextStartOver;
static GameStateSlotFn NextLoad, NextSave;

static unsigned char *Tree() { return (unsigned char *)SITE(FAMILY_TREE); }
static unsigned char *Manager() { return (unsigned char *)SITE(VILLAGER_MANAGER); }
static unsigned char *GameState() { return *(unsigned char **)SITE(GAME_STATE_INSTANCE); }
static int I32(const unsigned char *p, unsigned off) { return *(const int *)(p + off); }

static unsigned char *Villager(int slot) {
    if (slot < 0 || slot >= (int)LOGS_HOUSEHOLD_SLOTS) return 0;
    return Manager() + LOGS_VILLAGER_ARRAY_OFFSET + (unsigned)slot * LOGS_VILLAGER_STRIDE;
}

static int SlotOf(const void *villager) {
    if (!villager) return -1;
    unsigned off = (unsigned)villager - (unsigned)(Manager() + LOGS_VILLAGER_ARRAY_OFFSET);
    if (off % LOGS_VILLAGER_STRIDE || off / LOGS_VILLAGER_STRIDE >= LOGS_HOUSEHOLD_SLOTS) return -1;
    return (int)(off / LOGS_VILLAGER_STRIDE);
}

static bool Active(const unsigned char *v) { return v && v[LOGS_VILLAGER_ACTIVE] != 0; }

static int Generations() {
    int g = I32(Tree(), LOGS_TREE_GENERATIONS_FIELD);
    return g < 0 || g > (int)LOGS_TREE_GENERATIONS ? 0 : g;
}

static bool Evicted() { return I32(Tree(), LOGS_TREE_EVICTED) != 0; }

static unsigned char *Record(int gen) {
    if (gen <= 0 || gen > (int)LOGS_TREE_GENERATIONS) return 0;
    unsigned char *rec = Tree() + (unsigned)gen * LOGS_FAMILY_RECORD_SIZE - LOGS_FAMILY_RECORD_BASE;
    return rec[0] ? rec : 0;
}

static int RecordChildren(const unsigned char *rec) {
    int n = I32(rec, LOGS_RECORD_CHILD_COUNT);
    return n < 0 ? 0 : n > (int)LOGS_TREE_CHILDREN ? (int)LOGS_TREE_CHILDREN : n;
}

static unsigned char *Peep(unsigned char *rec, int which) {    // 0 parent 1, 1 parent 2, 2.. children
    if (which == 0) return rec + LOGS_RECORD_PARENT1;
    if (which == 1) return rec + LOGS_RECORD_PARENT2;
    return rec + LOGS_RECORD_CHILDREN + (unsigned)(which - 2) * LOGS_PEEP_RECORD_SIZE;
}

static int CurrentSlot() {
    unsigned char *gs = GameState();
    if (!gs) return 0;
    int s = I32(gs, LOGS_GAME_STATE_SLOT);
    return s >= 1 && s <= 5 ? s : 0;
}

// The family's name in the logs' header: the player's name the save slot carries (Virtual Families 2
// villagers have one name each and the save has no family name; docs/vf2-save-format.md section 4).
static const char *FamilyName() {
    unsigned char *gs = GameState();
    return gs ? (const char *)(gs + LOGS_GAME_STATE_NICKNAME) : "";
}

// The executable's own words.
static const char *Word(unsigned id) {
    ((SingletonFn)SITE(SM_GET))();
    const char *s = ((GetStringFn)SITE(SM_GET_STRING))((int)id);
    return s && (unsigned)s != SITE(STRING_MISSING) ? s : "";
}
static const char *SexWord(int sex) { return Word(sex == 1 ? LOGS_STR_FEMALE : LOGS_STR_MALE); }
static const char *CauseWord(int cause) {
    int id = (int)LOGS_STR_CAUSE_UNKNOWN + 1 + cause;      // -1 Unknown causes .. 4 Act of Nature
    if (id < (int)LOGS_STR_CAUSE_UNKNOWN || id > (int)LOGS_STR_CAUSE_LAST) id = (int)LOGS_STR_CAUSE_UNKNOWN;
    return Word((unsigned)id);
}

struct Person {
    int slot;
    int sex;
    int age;
    int head;
    int body;
    char name[28];
};

static void Capture(const unsigned char *v, Person &p) {
    Zero(&p, sizeof(p));
    p.slot = SlotOf(v);
    if (!v) { p.slot = -1; return; }
    p.sex = I32(v, LOGS_VILLAGER_GENDER);
    p.age = I32(v, LOGS_VILLAGER_AGE);
    p.head = I32(v, LOGS_VILLAGER_HEAD);
    p.body = I32(v, LOGS_VILLAGER_BODY);
    Copy(p.name, v + LOGS_VILLAGER_NAME, LOGS_VILLAGER_NAME_LEN);
    p.name[LOGS_VILLAGER_NAME_LEN] = 0;
}

static unsigned Years(int units) { return units < 0 ? 0u : (unsigned)units / LOGS_UNITS_PER_YEAR; }

// Where the villager stands in the current generation's Family Tree record: 0 parent 1, 1 parent 2,
// 2.. a child, -1 not in it. The record's slot is checked with the name, as the game's own records go stale.
static int TreeRole(const Person &p) {
    unsigned char *rec = Record(Generations());
    if (!rec || p.slot < 0) return -1;
    int n = 2 + RecordChildren(rec);
    for (int k = 0; k < n; ++k) {
        unsigned char *peep = Peep(rec, k);
        if (peep[LOGS_PEEP_VALID] && I32(peep, LOGS_PEEP_SLOT) == p.slot && SameText((const char *)peep, p.name, 25))
            return k;
    }
    return -1;
}

static const char *RoleText(int role) {
    return role == 0 ? "Parent" : role == 1 ? "Parent (married in)" : role >= 2 ? "Child" : "(not in the Family Tree)";
}

// ================================================================ files
static char ReadBuffer[0x100000];
static char Line[0x4000];
static char Body[0x4000];

enum { FILE_MISSING = 0, FILE_OK = 1, FILE_SHUT = -2 };

static int ReadWhole(const char *path, unsigned *got) {
    *got = 0;
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) {
        DWORD e = GetLastError();
        return e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND ? FILE_MISSING : FILE_SHUT;
    }
    DWORD n = 0;
    BOOL ok = ReadFile(h, ReadBuffer, sizeof(ReadBuffer) - 1, &n, 0);
    CloseHandle(h);
    if (!ok) return FILE_SHUT;
    ReadBuffer[n] = 0;
    *got = n;
    return FILE_OK;
}

static bool Exists(const char *path) { return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES; }

// Every folder from the save folder's drive down to `path`'s own folder.
static void MakeParents(const char *path) {
    char p[MAX_PATH + 64];
    unsigned n = Length(path);
    if (n >= sizeof(p)) return;
    Copy(p, path, n + 1);
    for (unsigned i = 3; i < n; ++i) {
        if (p[i] == '\\') {
            p[i] = 0;
            CreateDirectoryA(p, 0);
            p[i] = '\\';
        }
    }
}

static bool Append(const char *path, const char *text, unsigned len) {
    MakeParents(path);
    HANDLE h = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ, 0, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    BOOL ok = WriteFile(h, text, len, &written, 0) && written == len;
    CloseHandle(h);
    return ok != FALSE;
}

static bool WriteAtomic(const char *path, const char *text, unsigned len) {
    char temp[MAX_PATH + 72];
    unsigned n = Length(path);
    if (n + 5 > sizeof(temp)) return false;
    MakeParents(path);
    Copy(temp, path, n);
    Copy(temp + n, ".tmp", 5);
    HANDLE h = CreateFileA(temp, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    BOOL ok = WriteFile(h, text, len, &written, 0) && written == len;
    if (ok) ok = FlushFileBuffers(h);
    CloseHandle(h);
    if (!ok || !MoveFileExA(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(temp);
        return false;
    }
    return true;
}

// <save folder>\ (from the game's own save path, MakeGameStatePath, theGameState vtable +0Ch).
static bool SaveFolder(char *out, unsigned cap) {
    unsigned char *state = GameState();
    if (!state) return false;
    void **vtable = *(void ***)state;
    const char *save = ((MakePathFn)vtable[LOGS_LDW_PATH_VSLOT / 4])(state, 1);
    unsigned n = Length(save);
    if (!save || n == 0 || n + 1 >= MAX_PATH) return false;
    unsigned cut = n;
    while (cut > 0 && save[cut - 1] != '\\' && save[cut - 1] != '/') --cut;
    if (cut == 0 || cut + 1 >= cap) return false;
    Copy(out, save, cut);
    out[cut] = 0;
    return true;
}

static const char kSaves[] = "Virtual Families 2 Patcher\\Save ";

// <save folder>\Virtual Families 2 Patcher\Save <slot>
static bool SlotRoot(int slot, Text &t) {
    char folder[MAX_PATH];
    if (slot < 1 || slot > 5 || !SaveFolder(folder, sizeof(folder))) return false;
    t.S(folder).S(kSaves).U((unsigned)slot);
    return t.n + 120 < t.cap;
}

static bool LogFile(int slot, const char *sub, const char *stem, unsigned number, char *out, unsigned cap) {
    Text t;
    t.Init(out, cap);
    if (!SlotRoot(slot, t)) return false;
    t.S("\\Logs\\").S(sub).S("\\").S(stem);
    if (number) t.S(" ").U(number);
    t.S(".txt");
    return t.n + 8 < cap;
}

static bool SnapshotFile(int slot, const char *sub, const char *stem, char *out, unsigned cap) {
    Text t;
    t.Init(out, cap);
    if (!SlotRoot(slot, t)) return false;
    t.S("\\Logs\\").S(sub).S("\\").S(stem).S(" - Save ").U((unsigned)slot).S(".txt");
    return t.n + 8 < cap;
}

static bool DataFile(int slot, const char *kind, const char *stem, char *out, unsigned cap) {
    Text t;
    t.Init(out, cap);
    if (!SlotRoot(slot, t)) return false;
    t.S("\\Data\\").S(kind).S("\\").S(stem).S(" - Save ").U((unsigned)slot).S(".dat");
    return t.n + 8 < cap;
}

// "Family: <name> (Save <N>)" -- the header every log file opens with (the Virtual Villagers logs'
// "Village: <name> (Save <S>)").
static void Header(Text &t, int slot) {
    const char *name = FamilyName();
    t.S("Family: ");
    if (name[0]) t.Name(name, LOGS_GAME_STATE_NICKNAME_LEN - 1); else t.S("(no name)");
    t.S(" (Save ").U((unsigned)slot).S(")").NL();
}

// ================================================================ the append-only logs
enum { LOG_HISTORY = 0, LOG_BIRTHS = 1, LOG_DEATHS = 2, LOG_EVENTS = 3, LOG_COUNT = 4 };
struct LogKind { const char *sub; const char *stem; const char *roll; unsigned per; };
static const LogKind kLogs[LOG_COUNT] = {
    { "Family History", "Family History", "[", 2000 },
    { "Births and Conceptions", "Virtual Families 2 Births and Conceptions Log", "Conception ", 256 },
    { "Deaths", "Virtual Families 2 Deaths Log", "Death ", 256 },
    { "Events", "Virtual Families 2 Events Log", "Event ", 256 },
};
static const unsigned kMaxLogFiles = 4096;

// Lines of the text that start with `marker`, and the highest number printed right after it.
static void CountMarkers(const char *text, unsigned len, const char *marker, unsigned *count, unsigned *highest) {
    unsigned m = Length(marker);
    for (unsigned i = 0; i < len; ++i) {
        if ((i == 0 || text[i - 1] == '\n') && i + m <= len && StartsWith(text + i, marker)) {
            ++*count;
            unsigned v = 0, j = i + m;
            while (j < len && text[j] >= '0' && text[j] <= '9' && v < 100000000u) v = v * 10 + (unsigned)(text[j++] - '0');
            if (v > *highest) *highest = v;
        }
    }
}

// The newest file of a log (0 when none), and the next number of `marker` after every file's highest.
// The births log numbers conceptions and births separately ("Conception 3", "Birth 3"), so a marker
// is counted on its own; `rolled` counts the newest file's records of every kind it holds.
static unsigned NewestFile(int slot, int kind, const char *marker, unsigned *next, unsigned *rolled) {
    char path[MAX_PATH + 64];
    unsigned newest = 0, highest = 0;
    *rolled = 0;
    for (unsigned k = 1; k <= kMaxLogFiles; ++k) {
        if (!LogFile(slot, kLogs[kind].sub, kLogs[kind].stem, k, path, sizeof(path)) || !Exists(path)) break;
        newest = k;
        if (marker) {
            unsigned got = 0, count = 0;
            if (ReadWhole(path, &got) == FILE_OK) CountMarkers(ReadBuffer, got, marker, &count, &highest);
        }
    }
    if (newest) {
        unsigned got = 0, count = 0, ignored = 0;
        if (LogFile(slot, kLogs[kind].sub, kLogs[kind].stem, newest, path, sizeof(path)) && ReadWhole(path, &got) == FILE_OK) {
            CountMarkers(ReadBuffer, got, kLogs[kind].roll, &count, &ignored);
            if (kind == LOG_BIRTHS) CountMarkers(ReadBuffer, got, "Birth ", &count, &ignored);
        }
        *rolled = count;
    }
    if (next) *next = highest + 1;
    return newest;
}

// Appends one record (or history line) to the slot's log, rolling to a new numbered file when the newest
// one is full. `marker`: "Conception " etc. -- the record is numbered after the highest already printed in
// any of the log's files; 0: the text is written as it is. Returns the number given (or 1).
static unsigned WriteLog(int slot, int kind, const char *marker, const char *text) {
    char path[MAX_PATH + 64];
    unsigned next = 1, rolled = 0;
    unsigned newest = NewestFile(slot, kind, marker, &next, &rolled);
    unsigned file = newest ? newest : 1;
    if (newest && rolled >= kLogs[kind].per) file = newest + 1;
    if (!LogFile(slot, kLogs[kind].sub, kLogs[kind].stem, file, path, sizeof(path))) return 0;
    static char out[0x4400];
    Text t;
    t.Init(out, sizeof(out));
    if (!Exists(path)) Header(t, slot);
    if (marker) t.S(marker).U(next).NL();
    t.S(text);
    if (kind != LOG_HISTORY) t.NL();
    if (!Append(path, out, t.n)) return 0;
    ++B200Logs_Status.records;
    return marker ? next : 1;
}

// The file of each log, created with its header if there is none yet (the owner: every log is there from
// the moment the family is).
static void CreateLogs(int slot) {
    char path[MAX_PATH + 64];
    for (int kind = 0; kind < LOG_COUNT; ++kind) {
        unsigned rolled = 0;
        if (NewestFile(slot, kind, 0, 0, &rolled)) continue;
        if (!LogFile(slot, kLogs[kind].sub, kLogs[kind].stem, 1, path, sizeof(path))) return;
        Text t;
        t.Init(Line, sizeof(Line));
        Header(t, slot);
        Append(path, Line, t.n);
    }
}

static void Stamp(Text &t, bool backfilled) {
    if (backfilled) { t.S("[backfilled, no date] "); return; }
    SYSTEMTIME now;
    GetLocalTime(&now);
    t.S("[").U(now.wYear).S("-").Two(now.wMonth).S("-").Two(now.wDay).S(" ").Two(now.wHour).S(":")
        .Two(now.wMinute).S(":").Two(now.wSecond).S("] ");
}

// One line of the Family History.
static void History(int slot, const char *text, bool backfilled = false) {
    if (slot < 1) return;
    Text t;
    t.Init(Line, sizeof(Line));
    Stamp(t, backfilled);
    t.S(text).NL();
    WriteLog(slot, LOG_HISTORY, 0, Line);
}

static void PersonLines(Text &t, const char *indent, const Person &p) {
    t.S(indent).S("Sex: ").S(SexWord(p.sex)).NL();
    t.S(indent).S("Head: ").I(p.head).NL();
    t.S(indent).S("Body: ").I(p.body).NL();
}

static void PersonName(Text &t, const char *name) {
    if (name && name[0]) t.Name(name, 25); else t.S("(unknown)");
}

// ================================================================ the data files
// Every data file is text, versioned and tagged (first line), one tab-separated entry per line.

// ---- Parents: each baby's mother and father, written at conception (the birth cannot know the father).
static void AddParents(int slot, const Person &child, const char *mother, const char *father, const char *how) {
    char path[MAX_PATH + 64];
    if (!DataFile(slot, "Parents", "Virtual Families 2 Parents", path, sizeof(path))) return;
    Text t;
    t.Init(Line, sizeof(Line));
    if (!Exists(path)) t.S("VF2LOGS PARENTS 1").NL();
    t.S("child\t").I(child.slot).S("\t").Name(child.name, 25).S("\t").I(child.sex).S("\t").I(Generations()).S("\t")
        .Name(mother, 25).S("\t").Name(father, 25).S("\t").S(how).NL();
    Append(path, Line, t.n);
}

// The newest Parents entry of a child (slot, name and sex), its mother and father copied out.
static bool FindParents(int slot, const Person &child, char *mother, char *father) {
    char path[MAX_PATH + 64];
    unsigned got = 0;
    mother[0] = father[0] = 0;
    if (!DataFile(slot, "Parents", "Virtual Families 2 Parents", path, sizeof(path)) || ReadWhole(path, &got) != FILE_OK)
        return false;
    if (!StartsWith(ReadBuffer, "VF2LOGS PARENTS 1")) return false;
    char want[64];
    Text w;
    w.Init(want, sizeof(want));
    w.S("child\t").I(child.slot).S("\t").Name(child.name, 25).S("\t").I(child.sex).S("\t");
    bool found = false;
    char *p = ReadBuffer, *end = ReadBuffer + got;
    while (p < end) {
        char *eol = p;
        while (eol < end && *eol != '\n') ++eol;
        if (StartsWith(p, want)) {
            // child, slot, name, sex, generation, mother, father, how
            char *q = p;
            for (int tab = 0; tab < 5 && q < eol; ++q) if (*q == '\t') ++tab;
            unsigned k = 0;
            while (q < eol && *q != '\t' && *q != '\r' && k < 27) mother[k++] = *q++;
            mother[k] = 0;
            if (q < eol && *q == '\t') ++q;
            k = 0;
            while (q < eol && *q != '\t' && *q != '\r' && k < 27) father[k++] = *q++;
            father[k] = 0;
            found = true;
        }
        p = eol + 1;
    }
    return found;
}

// ---- The backfill marker: an existing family's past is written once. It also keeps how many deaths the
// Family Tree held when the logs began (the Deaths count of Family Statistics adds the logged ones).
static bool BackfillFile(int slot, char *path, unsigned cap) {
    return DataFile(slot, "Log Checks", "Virtual Families 2 Backfill", path, cap);
}

static void WriteBackfillMarker(int slot, const char *how, int deaths) {
    char path[MAX_PATH + 64];
    if (!BackfillFile(slot, path, sizeof(path))) return;
    Text t;
    t.Init(Line, sizeof(Line));
    t.S("VF2LOGS BACKFILL 1").NL().S("family\t").Name(FamilyName(), LOGS_GAME_STATE_NICKNAME_LEN - 1).NL()
        .S("how\t").S(how).NL().S("deaths\t").I(deaths).NL();
    WriteAtomic(path, Line, t.n);
}

static int ParseInt(const char *&p) {
    bool neg = *p == '-';
    if (neg) ++p;
    int v = 0;
    while (*p >= '0' && *p <= '9' && v < 100000000) v = v * 10 + (*p++ - '0');
    return neg ? -v : v;
}

static int BackfilledDeaths(int slot) {
    char path[MAX_PATH + 64];
    unsigned got = 0;
    if (!BackfillFile(slot, path, sizeof(path)) || ReadWhole(path, &got) != FILE_OK) return 0;
    if (!StartsWith(ReadBuffer, "VF2LOGS BACKFILL 1")) return 0;
    const char *p = ReadBuffer;
    while (*p) {
        if (StartsWith(p, "deaths\t")) { p += 7; int v = ParseInt(p); return v < 0 ? 0 : v; }
        while (*p && *p != '\n') ++p;
        if (*p) ++p;
    }
    return 0;
}

// ================================================================ wiping a slot (Start Over, a new family)
// Deletes everything in <save folder>\Virtual Families 2 Patcher\Save <slot>\ except a Backups folder in it.
static void DeleteTree(char *path, unsigned len, unsigned cap, bool top) {
    if (len + 4 >= cap) return;
    Copy(path + len, "\\*", 3);
    WIN32_FIND_DATAA found;
    HANDLE h = FindFirstFileA(path, &found);
    path[len] = 0;
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        const char *name = found.cFileName;
        if (name[0] == '.' && (name[1] == 0 || (name[1] == '.' && name[2] == 0))) continue;
        bool dir = (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        if (top && dir && SameNameIgnoringCase(name, "Backups")) continue;
        unsigned n = Length(name);
        if (len + 1 + n + 1 >= cap) continue;
        path[len] = '\\';
        Copy(path + len + 1, name, n + 1);
        if (dir) {
            DeleteTree(path, len + 1 + n, cap, false);
            RemoveDirectoryA(path);
        } else {
            if (found.dwFileAttributes & FILE_ATTRIBUTE_READONLY) SetFileAttributesA(path, FILE_ATTRIBUTE_NORMAL);
            DeleteFileA(path);
        }
        path[len] = 0;
    } while (FindNextFileA(h, &found));
    FindClose(h);
}

// Deaths already logged this session (each villager once).
struct Logged { int valid; int sex; int age; char name[28]; };
static Logged DeathLogged[LOGS_HOUSEHOLD_SLOTS];

static void ClearSession() { Zero(DeathLogged, sizeof(DeathLogged)); }

static bool WasLogged(const Person &p) {
    if (p.slot < 0) return false;
    const Logged &l = DeathLogged[p.slot];
    return l.valid && l.sex == p.sex && l.age == p.age && SameText(l.name, p.name, 25);
}

static void MarkLogged(const Person &p) {
    if (p.slot < 0) return;
    Logged &l = DeathLogged[p.slot];
    l.valid = 1;
    l.sex = p.sex;
    l.age = p.age;
    Copy(l.name, p.name, 28);
}

static void WipeSlot(int slot) {
    char path[MAX_PATH + 64];
    Text t;
    t.Init(path, sizeof(path));
    if (!SlotRoot(slot, t)) return;
    DeleteTree(path, t.n, sizeof(path), true);
    ClearSession();
    ++B200Logs_Status.wipes;
}

// ================================================================ the events
static int gInLoad;

// ---- conception
// The father: the household villager whose head and body are the ones Impregnate was given (both of its
// callers pass the father's own), the mother's spouse in the Family Tree first.
static unsigned char *FindFather(const unsigned char *mother, int head, int body) {
    unsigned char *rec = Record(Generations());
    int ms = SlotOf(mother);
    if (rec) {
        for (int k = 0; k < 2; ++k) {
            unsigned char *peep = Peep(rec, k);
            int s = I32(peep, LOGS_PEEP_SLOT);
            if (!peep[LOGS_PEEP_VALID] || s == ms) continue;
            unsigned char *v = Villager(s);
            if (Active(v) && I32(v, LOGS_VILLAGER_HEAD) == head && I32(v, LOGS_VILLAGER_BODY) == body) return v;
        }
    }
    for (int s = 0; s < (int)LOGS_HOUSEHOLD_SLOTS; ++s) {
        unsigned char *v = Villager(s);
        if (s == ms || !Active(v) || I32(v, LOGS_VILLAGER_HEALTH) <= 0) continue;
        if (I32(v, LOGS_VILLAGER_HEAD) == head && I32(v, LOGS_VILLAGER_BODY) == body) return v;
    }
    return 0;
}

static void OnConception(const unsigned char *mother, const unsigned char *father) {
    int slot = CurrentSlot();
    if (!slot) return;
    Person m, f;
    Capture(mother, m);
    Capture(father, f);
    const unsigned char *gs = GameState();
    int babies = I32(mother, LOGS_VILLAGER_CARRIED);
    Text t;
    t.Init(Body, sizeof(Body));
    t.S("  Mother: ").Name(m.name, 25).NL();
    t.S("    Age at conception: ").U(Years(m.age)).NL();
    PersonLines(t, "    ", m);
    t.S("  Father: ");
    PersonName(t, father ? f.name : 0);
    t.NL();
    if (father) {
        t.S("    Age at conception: ").U(Years(f.age)).NL();
        PersonLines(t, "    ", f);
    }
    t.S("  Babies ").S(Word(LOGS_STR_NURSING)).S(": ").I(babies).NL();
    t.S("  Generation: ").I(Generations()).NL();
    unsigned number = WriteLog(slot, LOG_BIRTHS, "Conception ", Body);
    for (int k = 0; gs && k < 3 && k < babies; ++k) {
        int b = I32(gs, LOGS_GAME_STATE_RESERVED_BABY + 4u * (unsigned)k);
        Person baby;
        Capture(Villager(b), baby);
        if (baby.slot >= 0) AddParents(slot, baby, m.name, father ? f.name : "", "conceived");
    }
    Text h;
    h.Init(Body, sizeof(Body));
    h.S("Conception ").U(number).S(": ").Name(m.name, 25).S(" and ");
    PersonName(h, father ? f.name : 0);
    h.S(" (babies ").S(Word(LOGS_STR_NURSING)).S(": ").I(babies).S(")");
    History(slot, Body);
}

// ---- births: what the physiology pass delivered
struct PassState {
    int reserved[3];
    int pregnant[LOGS_HOUSEHOLD_SLOTS];
    unsigned char present[LOGS_HOUSEHOLD_SLOTS];
};
static PassState Before;

static void SnapshotPass(PassState &s) {
    const unsigned char *gs = GameState();
    for (int k = 0; k < 3; ++k) s.reserved[k] = gs ? I32(gs, LOGS_GAME_STATE_RESERVED_BABY + 4u * (unsigned)k) : -1;
    for (int i = 0; i < (int)LOGS_HOUSEHOLD_SLOTS; ++i) {
        const unsigned char *v = Villager(i);
        s.pregnant[i] = I32(v, LOGS_VILLAGER_PREGNANT);
        s.present[i] = v[LOGS_VILLAGER_ACTIVE];
    }
}

static void OnBirths(int mother) {
    int slot = CurrentSlot();
    const unsigned char *gs = GameState();
    if (!slot || !gs) return;
    int born[3], n = 0;
    for (int k = 0; k < 3; ++k) {
        int b = Before.reserved[k];
        if (b < 0 || b >= (int)LOGS_HOUSEHOLD_SLOTS || b == mother) continue;
        if (I32(gs, LOGS_GAME_STATE_RESERVED_BABY + 4u * (unsigned)k) != -1) continue;
        if (Before.present[b] || !Active(Villager(b))) continue;
        born[n++] = b;
    }
    if (!n) return;
    Person m;
    Capture(Villager(mother), m);
    const char *bornAs = n == 1 ? "Single birth" : n == 2 ? "Twins" : "Triplets";
    for (int i = 0; i < n; ++i) {
        Person c;
        Capture(Villager(born[i]), c);
        char motherName[28], fatherName[28];
        if (!FindParents(slot, c, motherName, fatherName)) {
            Copy(motherName, m.name, 28);
            fatherName[0] = 0;
        }
        Text t;
        t.Init(Body, sizeof(Body));
        t.S("  Child: ").Name(c.name, 25).NL();
        PersonLines(t, "    ", c);
        t.S("  Mother: ").Name(m.name, 25).NL();
        t.S("    Head: ").I(m.head).NL().S("    Body: ").I(m.body).NL();
        t.S("  Father: ");
        PersonName(t, fatherName);
        t.NL();
        t.S("  Born as: ").S(bornAs).NL();
        t.S("  Generation: ").I(Generations()).NL();
        unsigned number = WriteLog(slot, LOG_BIRTHS, "Birth ", Body);
        Text h;
        h.Init(Body, sizeof(Body));
        h.S("Birth ").U(number).S(": ").Name(c.name, 25).S(" (").S(SexWord(c.sex)).S(") was born to ").Name(m.name, 25)
            .S(" and ");
        PersonName(h, fatherName);
        if (n > 1) h.S(" (").S(bornAs).S(")");
        History(slot, Body);
    }
}

// ---- deaths
static void OnDeath(const Person &p, int cause, int role, int gen) {
    int slot = CurrentSlot();
    if (!slot || WasLogged(p)) return;
    MarkLogged(p);
    Text t;
    t.Init(Body, sizeof(Body));
    t.S("  Name: ").Name(p.name, 25).NL();
    t.S("  Age at death: ").U(Years(p.age)).NL();
    t.S("  Sex: ").S(SexWord(p.sex)).NL();
    t.S("  Cause of death: ").S(CauseWord(cause)).NL();
    t.S("  Head: ").I(p.head).NL().S("  Body: ").I(p.body).NL();
    t.S("  Family role: ").S(RoleText(role)).NL();
    t.S("  Generation: ").I(gen).NL();
    unsigned number = WriteLog(slot, LOG_DEATHS, "Death ", Body);
    Text h;
    h.Init(Body, sizeof(Body));
    h.S("Death ").U(number).S(": ").Name(p.name, 25).S(" (").S(SexWord(p.sex)).S(", ").U(Years(p.age)).S(") died: ")
        .S(CauseWord(cause));
    History(slot, Body);
}

static void ReportDeath(TreeVillagerFn next, void *tree, void *villager) {
    const unsigned char *v = (const unsigned char *)villager;
    Person p;
    Capture(v, p);
    bool dead = v && I32(v, LOGS_VILLAGER_HEALTH) <= 0;
    int cause = v ? I32(v, LOGS_VILLAGER_CAUSE) : -1;
    int role = TreeRole(p);
    int gen = Generations();
    next(tree, villager);
    if (dead && p.slot >= 0 && !gInLoad) OnDeath(p, cause, role, gen);
}

// ---- marriage
static void OnMarriage(const Person &a, const Person &b) {
    int slot = CurrentSlot();
    if (!slot) return;
    Text h;
    h.Init(Body, sizeof(Body));
    h.Name(a.name, 25).S(" (").S(SexWord(a.sex)).S(", ").U(Years(a.age)).S(") married ").Name(b.name, 25).S(" (")
        .S(SexWord(b.sex)).S(", ").U(Years(b.age)).S("), generation ").I(Generations());
    History(slot, Body);
}

// ---- the Events log: the game's own family events that are not a birth or a death
static unsigned EventRecord(int slot, const char *title, const Person *p, bool members) {
    Text t;
    t.Init(Body, sizeof(Body));
    t.S("  Event: ").S(title).NL();
    if (p && p->slot >= 0 && p->name[0]) {
        t.S("  Name: ").Name(p->name, 25).NL();
        t.S("  Age: ").U(Years(p->age)).NL();
        PersonLines(t, "  ", *p);
    }
    if (members) {
        t.S("  Family members:");
        bool any = false;
        for (int s = 0; s < (int)LOGS_HOUSEHOLD_SLOTS; ++s) {
            unsigned char *v = Villager(s);
            if (!Active(v) || I32(v, LOGS_VILLAGER_HEALTH) <= 0) continue;
            t.S(any ? ", " : " ").Name((const char *)(v + LOGS_VILLAGER_NAME), 25);
            any = true;
        }
        if (!any) t.S(" (none)");
        t.NL();
    }
    t.S("  Generation: ").I(Generations()).NL();
    unsigned number = WriteLog(slot, LOG_EVENTS, "Event ", Body);
    Text h;
    h.Init(Body, sizeof(Body));
    h.S("Event ").U(number).S(": ").S(title);
    if (p && p->slot >= 0 && p->name[0]) h.S(": ").Name(p->name, 25);
    History(slot, Body);
    return number;
}

// ---- a child who joins (not a baby: babies are added at conception and logged at birth)
static void OnJoined(const unsigned char *v, const char *title) {
    int slot = CurrentSlot();
    if (!slot || !v) return;
    Person c;
    Capture(v, c);
    EventRecord(slot, title, &c, false);
    Text h;
    h.Init(Body, sizeof(Body));
    h.Name(c.name, 25).S(" (").S(SexWord(c.sex)).S(", ").U(Years(c.age)).S(") joined the family as a child, adopted");
    h.S(", generation ").I(Generations());
    History(slot, Body);
}

// ---- a generation begins (a new family, Next Generation)
static void OnGeneration(const unsigned char *v, bool newFamily, bool afterEviction) {
    int slot = CurrentSlot();
    if (!slot || !v) return;
    Person p;
    Capture(v, p);
    Text h;
    h.Init(Body, sizeof(Body));
    if (newFamily && afterEviction) {
        h.S("Generation 1 began after the eviction: ").Name(p.name, 25).S(" (").S(SexWord(p.sex)).S(", ")
            .U(Years(p.age)).S(") was adopted");
    } else if (newFamily) {
        // A brand-new family in this slot (a new game, or after Start Over): the slot's folder is the new
        // family's alone.
        WipeSlot(slot);
        CreateLogs(slot);
        WriteBackfillMarker(slot, "new family", 0);
        h.S("Generation 1 began: ").Name(p.name, 25).S(" (").S(SexWord(p.sex)).S(", ").U(Years(p.age))
            .S(") was adopted and started the family");
    } else {
        h.S(Word(LOGS_STR_NEW_GENERATION)).S(": generation ").I(Generations()).S(" began: ").Name(p.name, 25).S(" (")
            .S(SexWord(p.sex)).S(", ").U(Years(p.age)).S(") inherited the house");
    }
    History(slot, Body);
}

// ---- leaving home: college (the game's own picture caption), Boarding School, The Talent Scout
enum { LEFT_COLLEGE = 0, LEFT_BOARDING_SCHOOL = 1, LEFT_TALENT_SCOUT = 2 };

static void Caption(Text &h, const char *caption, const char *name) {
    for (const char *s = caption; *s;) {
        if (StartsWith(s, "{name}")) { h.Name(name, 25); s += 6; }
        else if (StartsWith(s, "%s")) { h.Name(name, 25); s += 2; }
        else { char c[2] = { *s++, 0 }; h.S(c); }
    }
}

static void OnLeftHome(const unsigned char *v, int why) {
    int slot = CurrentSlot();
    if (!slot || !v) return;
    Person p;
    Capture(v, p);
    if (why == LEFT_BOARDING_SCHOOL) EventRecord(slot, Word(LOGS_STR_BOARDING_SCHOOL), &p, false);
    if (why == LEFT_TALENT_SCOUT) EventRecord(slot, Word(LOGS_STR_TALENT_SCOUT), &p, false);
    Text h;
    h.Init(Body, sizeof(Body));
    if (why == LEFT_COLLEGE) Caption(h, Word(LOGS_STR_COLLEGE_TITLE), p.name);
    else if (why == LEFT_BOARDING_SCHOOL) Caption(h, Word(LOGS_STR_BOARDING_SENT), p.name);
    else h.Name(p.name, 25).S(" left home with ").S(Word(LOGS_STR_TALENT_SCOUT));
    h.S(" (").S(SexWord(p.sex)).S(", ").U(Years(p.age)).S(", left home)");
    History(slot, Body);
}

// ================================================================ save and load
// The balance is a double (CMoney+0); whole coins, no C runtime.
static unsigned Dollars(const void *money) {
    unsigned lo = ((const unsigned *)money)[0], hi = ((const unsigned *)money)[1];
    if (hi >> 31) return 0;
    int exponent = (int)((hi >> 20) & 0x7FF) - 1023;
    if (exponent < 0) return 0;
    if (exponent > 31) return 0xFFFFFFFFu;
    unsigned long long mantissa = ((unsigned long long)(hi & 0xFFFFF) << 32 | lo) | (1ull << 52);
    return (unsigned)(mantissa >> (52 - exponent));
}

static void WritePopulation(int slot) {
    char path[MAX_PATH + 64];
    if (!SnapshotFile(slot, "Family Population", "Family Population", path, sizeof(path))) return;
    static char out[0x10000];
    Text t;
    t.Init(out, sizeof(out));
    t.S("Virtual Families 2 Family Population").NL();
    Header(t, slot);
    t.S("Generation: ").I(Generations()).NL();
    unsigned k = 0;
    for (int s = 0; s < (int)LOGS_HOUSEHOLD_SLOTS; ++s) {
        unsigned char *v = Villager(s);
        if (!Active(v)) continue;
        Person p;
        Capture(v, p);
        int role = TreeRole(p);
        t.NL().S("Family Member ").U(++k).NL();
        t.S("  Name: ").Name(p.name, 25).NL();
        t.S("  Age: ").U(Years(p.age)).NL();
        PersonLines(t, "  ", p);
        t.S("  Family role: ").S(RoleText(role)).NL();
        int health = I32(v, LOGS_VILLAGER_HEALTH);
        t.S("  Health: ").I(health).NL();
        if (health <= 0) t.S("  Cause of death: ").S(CauseWord(I32(v, LOGS_VILLAGER_CAUSE))).NL();
        if (I32(v, LOGS_VILLAGER_PREGNANT)) {
            t.S("  ").S(Word(LOGS_STR_NURSING)).S(": yes").NL();
            t.S("  Babies ").S(Word(LOGS_STR_NURSING)).S(": ").I(I32(v, LOGS_VILLAGER_CARRIED)).NL();
        }
        if (v[LOGS_VILLAGER_LEFT_HOME]) t.S("  Left home: yes").NL();
    }
    if (!k) t.NL().S("(nobody)").NL();
    WriteAtomic(path, out, t.n);
}

static void WriteStatistics(int slot) {
    char path[MAX_PATH + 64];
    if (!SnapshotFile(slot, "Family Statistics", "Family Statistics", path, sizeof(path))) return;
    unsigned members = 0;
    for (int s = 0; s < (int)LOGS_HOUSEHOLD_SLOTS; ++s) {
        unsigned char *v = Villager(s);
        if (Active(v) && !v[LOGS_VILLAGER_LEFT_HOME] && I32(v, LOGS_VILLAGER_HEALTH) > 0) ++members;
    }
    // Babies Born: the game's own count (Impregnate adds each pregnancy's babies), less those not born yet.
    int babies = *(const int *)SITE(GAME_STATS_BABIES);
    const unsigned char *gs = GameState();
    for (int k = 0; gs && k < 3; ++k) if (I32(gs, LOGS_GAME_STATE_RESERVED_BABY + 4u * (unsigned)k) != -1) --babies;
    if (babies < 0) babies = 0;
    // Deaths: the ones the Family Tree held when the logs began, and every one logged since.
    unsigned next = 1, rolled = 0;
    NewestFile(slot, LOG_DEATHS, "Death ", &next, &rolled);
    int deaths = BackfilledDeaths(slot) + (int)(next - 1);
    Text t;
    t.Init(Line, sizeof(Line));
    t.S("Virtual Families 2").NL().S("Family Statistics").NL();
    Header(t, slot);
    t.NL();
    t.S("Generations: ").I(Generations()).NL();
    t.S("Family Members: ").U(members).NL();
    t.S("Babies Born: ").I(babies).NL();
    t.S("Deaths: ").I(deaths).NL();
    t.S("Oldest Family Member Ever: ").I(*(const int *)SITE(GAME_STATS_OLDEST)).NL();
    t.S("Money: $").U(Dollars((const void *)SITE(MONEY))).NL();
    int food = *(const int *)(SITE(FOOD_STORE) + LOGS_FOOD_OFFSET);
    t.S("Food: ").I(food < 0 ? 0 : food).NL();
    WriteAtomic(path, Line, t.n);
}

// An existing family seen for the first time: its past generations, from the save's Family Tree, once.
// Returns the deaths the tree records (a slot of -1).
static int Backfill(int slot) {
    int gens = Generations();
    int deaths = 0;
    for (int g = 1; g <= gens; ++g) {
        unsigned char *rec = Record(g);
        if (!rec) continue;
        Text h;
        h.Init(Body, sizeof(Body));
        unsigned char *p1 = Peep(rec, 0), *p2 = Peep(rec, 1);
        h.S("Generation ").I(g).S(": ");
        if (p1[LOGS_PEEP_VALID]) h.Name((const char *)p1, 25).S(" (").S(SexWord(I32(p1, LOGS_PEEP_GENDER))).S(")");
        else h.S("(nobody)");
        if (p2[LOGS_PEEP_VALID]) h.S(" and ").Name((const char *)p2, 25).S(" (").S(SexWord(I32(p2, LOGS_PEEP_GENDER))).S(")");
        h.S(p2[LOGS_PEEP_VALID] ? " were the parents" : " was the parent");
        History(slot, Body, true);
        int n = RecordChildren(rec);
        for (int c = 0; c < n; ++c) {
            unsigned char *kid = Peep(rec, 2 + c);
            if (!kid[LOGS_PEEP_VALID]) continue;
            Text k;
            k.Init(Body, sizeof(Body));
            k.S("Generation ").I(g).S(": child ").Name((const char *)kid, 25).S(" (").S(SexWord(I32(kid, LOGS_PEEP_GENDER)))
                .S(")");
            if (I32(kid, LOGS_PEEP_SLOT) == -1) { k.S(", died"); ++deaths; }
            History(slot, Body, true);
        }
        for (int k = 0; k < 2; ++k) {
            unsigned char *parent = Peep(rec, k);
            if (!parent[LOGS_PEEP_VALID] || I32(parent, LOGS_PEEP_SLOT) != -1) continue;
            ++deaths;
            Text d;
            d.Init(Body, sizeof(Body));
            d.S("Generation ").I(g).S(": ").Name((const char *)parent, 25).S(" died");
            History(slot, Body, true);
        }
    }
    return deaths;
}

static void BackfillOrCreate(int slot) {
    char path[MAX_PATH + 64];
    if (!BackfillFile(slot, path, sizeof(path))) return;
    bool marked = Exists(path);
    unsigned rolled = 0;
    bool history = NewestFile(slot, LOG_HISTORY, 0, 0, &rolled) != 0;
    CreateLogs(slot);
    B200Logs_Status.lastLoad = 1;
    if (marked) return;
    if (history && rolled > 0) {           // logs already began here (an older marker was lost): never twice
        WriteBackfillMarker(slot, "logs found", 0);
        return;
    }
    if (Generations() <= 0) return;        // no family yet: the new family's adoption starts the logs
    int deaths = Backfill(slot);
    WriteBackfillMarker(slot, "backfilled", deaths);
    B200Logs_Status.lastLoad = 2;
}

// ================================================================ the hooks
static bool __fastcall ImpregnateHook(void *mother, void *, int one, const char *father, int head, int body, int flag) {
    unsigned char *dad = FindFather((const unsigned char *)mother, head, body);
    bool ok = OrigImpregnate(mother, one, father, head, body, flag);
    if (ok && !gInLoad) OnConception((const unsigned char *)mother, dad);
    return ok;
}

static void __fastcall PhysiologyHook(void *manager, void *) {
    SnapshotPass(Before);
    NextPhysiology(manager);
    for (int i = 0; i < (int)LOGS_HOUSEHOLD_SLOTS; ++i)
        if (Before.pregnant[i] && !I32(Villager(i), LOGS_VILLAGER_PREGNANT)) OnBirths(i);
}

static void __fastcall DeathTimeflowHook(void *tree, void *, void *villager) { ReportDeath(NextDeathTimeflow, tree, villager); }
static void __fastcall DeathBehaviorHook(void *tree, void *, void *villager) { ReportDeath(NextDeathBehavior, tree, villager); }

static void LeftHome(ThisVoidFn next, void *villager, int why) {
    bool was = ((unsigned char *)villager)[LOGS_VILLAGER_LEFT_HOME] != 0;
    next(villager);
    if (!was && !gInLoad) OnLeftHome((const unsigned char *)villager, why);
}
static void __fastcall CollegeHook(void *villager, void *) { LeftHome(NextCollege, villager, LEFT_COLLEGE); }
static void __fastcall BoardingSchoolHook(void *villager, void *) { LeftHome(NextBoardingSchool, villager, LEFT_BOARDING_SCHOOL); }
static void __fastcall TalentScoutHook(void *villager, void *) { LeftHome(NextTalentScout, villager, LEFT_TALENT_SCOUT); }

static bool __fastcall MarriageHook(void *tree, void *, void *a, void *b) {
    Person pa, pb;
    Capture((const unsigned char *)a, pa);
    Capture((const unsigned char *)b, pb);
    bool ok = NextMarriage(tree, a, b);
    if (ok && !gInLoad) OnMarriage(pa, pb);
    return ok;
}

static bool __fastcall NewFamilyHook(void *tree, void *, void *villager) {
    bool afterEviction = Evicted();
    bool ok = NextNewFamily(tree, villager);
    if (ok && !gInLoad) OnGeneration((const unsigned char *)villager, true, afterEviction);
    return ok;
}

static bool __fastcall NextGenerationHook(void *tree, void *, void *villager, int source) {
    bool ok = NextNextGeneration(tree, villager, source);
    if (ok && !gInLoad) OnGeneration((const unsigned char *)villager, false, false);
    return ok;
}

static bool Joined(TreeVillagerBoolFn next, void *tree, void *villager, unsigned title) {
    bool ok = next(tree, villager);
    if (ok && !gInLoad) OnJoined((const unsigned char *)villager, Word(title));
    return ok;
}
static bool __fastcall LittleVisitor1Hook(void *tree, void *, void *v) { return Joined(NextLittleVisitor1, tree, v, LOGS_STR_LITTLE_VISITOR); }
static bool __fastcall LittleVisitor2Hook(void *tree, void *, void *v) { return Joined(NextLittleVisitor2, tree, v, LOGS_STR_LITTLE_VISITOR); }
static bool __fastcall AdoptionHook(void *tree, void *, void *v) { return Joined(NextAdoption, tree, v, LOGS_STR_ADOPTION); }

// Evict Family keeps the slot's logs: the eviction is an Event (with the household it sends away, logged
// before the household is removed), and the next family's first generation is "after the eviction".
static void __fastcall EvictHook(void *tree, void *) {
    int slot = CurrentSlot();
    if (slot && !gInLoad) EventRecord(slot, "Evict Family", 0, true);
    NextEvict(tree);
}

static void __fastcall StartOverHook(void *state, void *) {
    int slot = CurrentSlot();
    if (slot) WipeSlot(slot);
    NextStartOver(state);
}

static bool __fastcall LoadHook(void *state, void *, int slot) {
    ++gInLoad;
    bool ok = NextLoad(state, slot);
    --gInLoad;
    if (ok && slot >= 1 && slot <= 5) {
        ClearSession();
        BackfillOrCreate(slot);
    }
    return ok;
}

static bool __fastcall SaveHook(void *state, void *, int slot) {
    bool ok = NextSave(state, slot);
    if (ok && slot >= 1 && slot <= 5) {
        char folder[MAX_PATH];
        if (!SaveFolder(folder, sizeof(folder))) { B200Logs_Status.lastSave = 2; return ok; }
        WritePopulation(slot);
        WriteStatistics(slot);
        B200Logs_Status.lastSave = 1;
    }
    return ok;
}

// ================================================================ plan and install
static const unsigned kMaxWrites = 24;

struct HookWrite {
    unsigned va;
    unsigned len;          // 5 (code) or 4 (a vtable slot)
    bool data;
    unsigned char bytes[5];
    unsigned char original[5];
};

struct Plan {
    HookWrite writes[kMaxWrites];
    unsigned count;
};

// The trampoline of the entry hook: the stolen instructions, then a jmp back. In a page of this DLL's own
// data that is made executable for it.
__declspec(align(4096)) static unsigned char Trampolines[4096];

static void *CallHandler(unsigned site) {
    switch (site) {
    case LOGS_SITE_CALL_PHYSIOLOGY: return (void *)&PhysiologyHook;
    case LOGS_SITE_CALL_DEATH_TIMEFLOW: return (void *)&DeathTimeflowHook;
    case LOGS_SITE_CALL_DEATH_BEHAVIOR: return (void *)&DeathBehaviorHook;
    case LOGS_SITE_CALL_COLLEGE: return (void *)&CollegeHook;
    case LOGS_SITE_CALL_BOARDING_SCHOOL: return (void *)&BoardingSchoolHook;
    case LOGS_SITE_CALL_TALENT_SCOUT: return (void *)&TalentScoutHook;
    case LOGS_SITE_CALL_MARRIAGE: return (void *)&MarriageHook;
    case LOGS_SITE_CALL_NEW_FAMILY: return (void *)&NewFamilyHook;
    case LOGS_SITE_CALL_NEXT_GENERATION: return (void *)&NextGenerationHook;
    case LOGS_SITE_CALL_LITTLE_VISITOR1: return (void *)&LittleVisitor1Hook;
    case LOGS_SITE_CALL_LITTLE_VISITOR2: return (void *)&LittleVisitor2Hook;
    case LOGS_SITE_CALL_ADOPTION: return (void *)&AdoptionHook;
    case LOGS_SITE_CALL_EVICT: return (void *)&EvictHook;
    case LOGS_SITE_CALL_START_OVER: return (void *)&StartOverHook;
    }
    return 0;
}

static void SetCallNext(unsigned site, unsigned target) {
    switch (site) {
    case LOGS_SITE_CALL_PHYSIOLOGY: NextPhysiology = (ThisVoidFn)target; break;
    case LOGS_SITE_CALL_DEATH_TIMEFLOW: NextDeathTimeflow = (TreeVillagerFn)target; break;
    case LOGS_SITE_CALL_DEATH_BEHAVIOR: NextDeathBehavior = (TreeVillagerFn)target; break;
    case LOGS_SITE_CALL_COLLEGE: NextCollege = (ThisVoidFn)target; break;
    case LOGS_SITE_CALL_BOARDING_SCHOOL: NextBoardingSchool = (ThisVoidFn)target; break;
    case LOGS_SITE_CALL_TALENT_SCOUT: NextTalentScout = (ThisVoidFn)target; break;
    case LOGS_SITE_CALL_MARRIAGE: NextMarriage = (UpdateParentsFn)target; break;
    case LOGS_SITE_CALL_NEW_FAMILY: NextNewFamily = (TreeVillagerBoolFn)target; break;
    case LOGS_SITE_CALL_NEXT_GENERATION: NextNextGeneration = (NextGenerationFn)target; break;
    case LOGS_SITE_CALL_LITTLE_VISITOR1: NextLittleVisitor1 = (TreeVillagerBoolFn)target; break;
    case LOGS_SITE_CALL_LITTLE_VISITOR2: NextLittleVisitor2 = (TreeVillagerBoolFn)target; break;
    case LOGS_SITE_CALL_ADOPTION: NextAdoption = (TreeVillagerBoolFn)target; break;
    case LOGS_SITE_CALL_EVICT: NextEvict = (ThisVoidFn)target; break;
    case LOGS_SITE_CALL_START_OVER: NextStartOver = (ThisVoidFn)target; break;
    }
}

static unsigned PinOfSite(unsigned site) {
    for (unsigned e = 0; e < sizeof(LOGS_EVIDENCE) / sizeof(LOGS_EVIDENCE[0]); ++e)
        if (LOGS_EVIDENCE[e].site == site && LOGS_EVIDENCE[e].kind == 'L' && LOGS_EVIDENCE[e].offset == 0)
            return LOGS_EVIDENCE[e].pin;
    return 0xFFFFFFFFu;
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

// A vtable slot holds the stock function, or a handler outside the executable (the Time Controls DLL's):
// either is chained to.
static bool SlotChain(unsigned slotVa, unsigned stock, unsigned *now) {
    *now = *(const unsigned *)slotVa;
    return *now == stock || (*now && !InImage(*now));
}

// Builds every write and the trampoline (the trampoline is this DLL's memory; nothing of the game is
// written here).
static bool PlanHooks(Plan &plan) {
    plan.count = 0;
    for (unsigned h = 0; h < sizeof(LOGS_CALL_HOOKS) / sizeof(LOGS_CALL_HOOKS[0]); ++h) {
        const LogsCallHook &hook = LOGS_CALL_HOOKS[h];
        unsigned site = Sites[hook.site];
        void *handler = CallHandler(hook.site);
        if (!handler || *(const unsigned char *)site != 0xE8) return false;
        unsigned target = site + 5 + *(const unsigned *)(site + 1);
        if (target != Sites[hook.function]) return false;
        SetCallNext(hook.site, target);
        HookWrite *w = AddWrite(plan, site, 5, false);
        if (!w) return false;
        w->bytes[0] = 0xE8;
        *(int *)(w->bytes + 1) = (int)((unsigned)handler - (site + 5));
    }
    unsigned used = 0;
    for (unsigned h = 0; h < sizeof(LOGS_ENTRY_HOOKS) / sizeof(LOGS_ENTRY_HOOKS[0]); ++h) {
        const LogsEntryHook &hook = LOGS_ENTRY_HOOKS[h];
        unsigned entry = Sites[hook.site];
        unsigned pin = PinOfSite(hook.site);
        if (pin >= kPinCount || hook.site != LOGS_SITE_V_IMPREGNATE || hook.steal < 5 || hook.steal > 16) return false;
        for (unsigned k = 0; k < hook.steal; ++k)
            if (LOGS_PINS[pin].mask[k] || ((const unsigned char *)entry)[k] != LOGS_PINS[pin].bytes[k]) return false;
        if (used + hook.steal + 5 > sizeof(Trampolines)) return false;
        unsigned char *t = Trampolines + used;
        Copy(t, (const void *)entry, hook.steal);
        t[hook.steal] = 0xE9;
        *(int *)(t + hook.steal + 1) = (int)((entry + hook.steal) - ((unsigned)t + hook.steal + 5));
        OrigImpregnate = (ImpregnateFn)(void *)t;
        used += (hook.steal + 5 + 15) & ~15u;
        HookWrite *w = AddWrite(plan, entry, 5, false);
        if (!w) return false;
        w->bytes[0] = 0xE9;
        *(int *)(w->bytes + 1) = (int)((unsigned)&ImpregnateHook - (entry + 5));
    }
    unsigned load = 0, save = 0;
    unsigned vt = SITE(GS_VTABLE);
    if (!SlotChain(vt + LOGS_GS_LOAD_VSLOT, SITE(GS_LOAD), &load) || !SlotChain(vt + LOGS_GS_SAVE_VSLOT, SITE(GS_SAVE), &save))
        return false;
    NextLoad = (GameStateSlotFn)load;
    NextSave = (GameStateSlotFn)save;
    HookWrite *wl = AddWrite(plan, vt + LOGS_GS_LOAD_VSLOT, 4, true);
    HookWrite *ws = AddWrite(plan, vt + LOGS_GS_SAVE_VSLOT, 4, true);
    if (!wl || !ws) return false;
    *(unsigned *)wl->bytes = (unsigned)&LoadHook;
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
    DWORD old = 0;
    if (!VirtualProtect(Trampolines, sizeof(Trampolines), PAGE_EXECUTE_READWRITE, &old)) return false;
    for (unsigned i = 0; i < plan.count; ++i) {
        HookWrite &w = plan.writes[i];
        for (unsigned j = 0; j < w.len; ++j) w.original[j] = ((const unsigned char *)w.va)[j];
        if (!WriteCode(w, w.bytes)) {
            Log("a write failed; restoring the earlier writes");
            for (unsigned j = 0; j < i; ++j) WriteCode(plan.writes[j], plan.writes[j].original);
            B200Logs_Status.writeMask = 0;
            return false;
        }
        B200Logs_Status.writeMask |= 1u << i;
    }
    return true;
}

static bool SettingOn() {
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    while (Folder[n] && n + 12 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *name = L"vf2logs.ini";
    for (unsigned i = 0; name[i]; ++i) path[n++] = name[i];
    path[n] = 0;
    return GetPrivateProfileIntW(L"Patches", L"FamilyLogs", 0, path) == 1;
}

// Called once by the executable's loader, before the game loop starts.
extern "C" __declspec(dllexport) void __cdecl B200Logs_Startup() {
    static bool started = false;
    if (started) return;
    started = true;
    DWORD n = GetModuleFileNameW(ThisModule, Folder, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    unsigned cut = n;
    while (cut > 0 && Folder[cut - 1] != L'\\') --cut;
    if (!cut) return;
    Folder[cut] = 0;
    Log("vf2logs_b200 started");
    bool on = SettingOn();
    B200Logs_Status.requested = on ? 1u : 0u;
    static Plan plan;
    int built = BuildPlan(on, plan);
    if (built == 0) { Log("Family Logs is off: the game is stock"); return; }
    if (built < 0) { Log("the executable could not be proved: installing nothing"); return; }
    B200Logs_Status.resolved = 1;
    ClearSession();
    if (Apply(plan)) {
        B200Logs_Status.installed = 1;
        Log("Family Logs installed");
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
#ifdef B200LOGS_TEST
extern "C" __declspec(dllexport) unsigned __cdecl B200Logs_TestScanAddress() { return (unsigned)&ScanPattern; }
extern "C" __declspec(dllexport) void __cdecl B200Logs_TestSetModule(unsigned module) { ThisModule = (HMODULE)module; }
extern "C" __declspec(dllexport) void __cdecl B200Logs_TestSites(unsigned *out) {
    for (unsigned i = 0; i < LOGS_SITE_COUNT; ++i) out[i] = Sites[i];
}
// Plans without writing. out: [status, count, then per write: va, len, data, bytes0..3, byte4].
extern "C" __declspec(dllexport) int __cdecl B200Logs_TestPlan(int enabled, unsigned *out) {
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
    if (built > 0) {
        DWORD old = 0;
        VirtualProtect(Trampolines, sizeof(Trampolines), PAGE_EXECUTE_READWRITE, &old);
    }
    return built;
}
#endif
