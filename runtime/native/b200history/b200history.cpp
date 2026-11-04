// vf2history_b200.dll -- "Family History", the companion DLL for the B200 Virtual Families 2 executable. One
// feature, one DLL: nothing else is installed here.
//
// It writes ONE log, the Family History, of every family event Virtual Families 2 has, for the Family Tree Maker,
// in the records of the Virtual Families 1 Family History log (vf1logs.dll, VF1 feat/family-history), which are the
// Virtual Villagers Fun Patcher's records with family words: a heading "[YYYY-MM-DD HH:MM:SS] <Kind> <n>" (numbered
// per kind across the slot's files), its "  Label: value" lines (a family member's own lines one step further in),
// then a blank line; a family member is written as the Virtual Villagers patcher writes a villager (the name, then
// the age, sex, head and body). Virtual Families 2 keeps no history (docs/vf2-save-format.md section 9), so each
// record is written at the moment the game makes the event, from the game's own memory, with the game's own words
// where it has them (theStringManager: "Male", "Female", "Nursing", the causes of death, "New Generation",
// "{name} is going to college!", "Adoption Services", "The Little Visitor", "The Talent Scout", and each Random
// Event's own title). Virtual Families 2 has no family surname: the header names the family by the player name the
// save holds (gs+25ABCh), as Rename Family does. Per save slot, beside the save, and nothing else:
//
//   <save folder>\Virtual Families 2 Patcher\Save <N>\Logs\Family History\Family History <k>.txt
//
// The file opens with "Family: <name> (Save <N>)"; after 2000 records the next one opens file <k+1>. A new family
// (the adoption of a founder, unless it follows Evict Family) and Start Over delete that slot's folder, Backups
// excepted; an existing family seen for the first time gets its Family Tree as "[backfilled, no date] Family
// Tree <n>" records, once (never when the log already holds a record).
//
// The B200 executable is RELOCATED (DYNAMICBASE) and each matrix variant links to different addresses, so this
// DLL holds NO game address. b200history_sites.h (generated and proved by runtime/tools/gen_b200_history_sites.py)
// holds pinned runs of the core variant with wildcards where a relocated field, a call displacement or another
// companion's entry hook sits; Resolve() finds every run in the live image exactly once and derives each
// address from where they were found.
//
// The executable's dormant loader (.vf2hist byte, 0 as built) loads this DLL only when the patcher setting is
// on, after the Time Controls and Up to 28 Children DLLs, and calls B200History_Startup() once before the game
// loop. Installing is: setting -> resolve -> plan -> apply, all or nothing. With the setting off, or anything
// the resolver cannot prove, NOTHING is written and the game is B200's own bytes. What it writes: 18 call
// retargets (each call goes to a handler here that makes the same call), one entry jmp (CVillager::Impregnate,
// 6 bytes stolen into a trampoline), and theGameState's Load vtable slot (chained to whatever it holds: the
// stock function or the Time Controls handler).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include "b200history_sites.h"
#include "b200name_limit.h"      // kNameBoxBytes: the one name limit (src/vf2_game_text.py)
#include "b200names_file.h"      // the Names file: header, CRC-32, one record (the Unicode text DLL writes it)
#include "b200unicode_text.h"    // the stored form and characters, as the Unicode text DLL reads the Names file

// Names (docs/UNICODE_TEXT.md, "Names up to 1,200 bytes"; runtime/native/b200unicode/b200names.inc): with a Unicode
// text setting on, a name longer than its save field is kept in the save as a SHORT FORM ("Maximilianus Fi...",
// "2...") and whole in the slot's Names file, <save folder>\Virtual Families 2 Patcher Data\Names\<save file>.txt.
// The log writes WHOLE names, as the Virtual Families 1 Family History does and as the game shows them: a name that
// ends with "..." is looked up in the Names file the way the Unicode text DLL's draw path looks it up (the current
// slot's file first, then the others'; the file read again when a short form is not yet known, since the Unicode
// text DLL writes it the moment a name is typed). A name the file does not hold, or no file, is written exactly as
// the save holds it (the patcher's readers, src/vf2_family_history.py, still expand old short forms themselves).

// ---------------------------------------------------------------- the sites
static unsigned Sites[HIST_SITE_COUNT];
#define SITE(name) (Sites[HIST_SITE_##name])

// ---------------------------------------------------------------- status block
// B200History_Status: what this launch installed and what the log did.
//   magic 'B2HI', version, requested, resolved, installed, writeMask (bit w: write w live),
//   records (Family History records written this session), lastLoad (0 none, 1 log created / found,
//   2 backfilled), wipes.
struct HistStatus {
    unsigned magic;
    unsigned version;
    unsigned requested;
    unsigned resolved;
    unsigned installed;
    unsigned writeMask;
    unsigned records;
    unsigned lastLoad;
    unsigned wipes;
};
extern "C" __declspec(dllexport) volatile HistStatus B200History_Status = { HIST_STATUS_MAGIC, 2u, 0, 0, 0, 0, 0, 0, 0 };

static HMODULE ThisModule;
static wchar_t Folder[MAX_PATH];

static void *Alloc(unsigned n) { return HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, n); }
static void Release(void *p) { if (p) HeapFree(GetProcessHeap(), 0, p); }

// The whole name a stored name (at most `max` bytes) is the short form of, nul-terminated; 0 when it is none.
static const char *WholeName(const char *stored, unsigned max);

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
    Text &Name(const char *s, unsigned max) {   // a game text field: at most `max` bytes, tabs and line ends dropped
        for (unsigned i = 0; s && i < max && s[i] && n + 1 < cap; ++i)
            if (s[i] != '\t' && s[i] != '\r' && s[i] != '\n') buf[n++] = s[i];
        buf[n] = 0;
        return *this;
    }
    // Game text (a name, a title) in the log's UTF-8: read with the stored form's per-sequence rule (a valid UTF-8
    // sequence stays, any other byte is its Windows-1252 character), at most `max` bytes, tabs and line ends dropped.
    Text &Utf8(const char *s, unsigned max) {
        const unsigned char *u = (const unsigned char *)s;
        unsigned len = 0;
        while (u && len < max && u[len]) ++len;
        unsigned cp, k;
        unsigned char seq[4];
        for (unsigned i = 0; i < len; i += k) {
            k = ut::ReadChar(u, len, i, &cp);
            if (cp == '\t' || cp == '\r' || cp == '\n') continue;
            unsigned m = ut::PutUtf8(cp, seq);
            if (n + m >= cap) break;
            for (unsigned j = 0; j < m; ++j) buf[n++] = (char)seq[j];
        }
        buf[n] = 0;
        return *this;
    }
    Text &Whole(const char *s, unsigned max) {  // a name field: the whole name its short form stands for, else itself
        const char *w = WholeName(s, max);
        return w ? Utf8(w, kNameBoxBytes) : Utf8(s, max);
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
// vf2history.log beside the DLL: what this launch installed (as vf2time.log and vf2kids.log). Not in the
// emulator test build.
static bool LogStarted;

#ifdef B200HISTORY_TEST
static void Log(const char *, const char * = 0) {}
#else
static void Log(const char *what, const char *name = 0) {
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    while (Folder[n] && n + 16 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *file = L"vf2history.log";
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

#ifdef B200HISTORY_TEST
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

static const unsigned kPinCount = sizeof(HIST_PINS) / sizeof(HIST_PINS[0]);
static unsigned PinAt[kPinCount];

static bool Resolve() {
    static ImageRange code[kMaxRanges];
    unsigned codeCount = 0;
    if (!ExecutableSections(code, &codeCount) || !codeCount) return false;
    for (unsigned i = 0; i < kPinCount; ++i) PinAt[i] = 0;
    for (unsigned i = 0; i < kPinCount; ++i) {
        const HistPin &pin = HIST_PINS[i];
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
            const HistPin &pin = HIST_PINS[i];
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
    for (unsigned i = 0; i < kPinCount; ++i) if (!PinAt[i]) { Log("a pin never resolved", HIST_PINS[i].name); return false; }
    bool have[HIST_SITE_COUNT];
    for (unsigned i = 0; i < HIST_SITE_COUNT; ++i) have[i] = false;
    for (unsigned e = 0; e < sizeof(HIST_EVIDENCE) / sizeof(HIST_EVIDENCE[0]); ++e) {
        const HistEvidence &ev = HIST_EVIDENCE[e];
        unsigned at = PinAt[ev.pin] + ev.offset;
        unsigned v = ev.kind == 'L' ? at : *(const unsigned *)at;
        if (have[ev.site] && Sites[ev.site] != v) { Log("two derivations of a site disagree"); return false; }
        Sites[ev.site] = v;
        have[ev.site] = true;
    }
    for (unsigned i = 0; i < HIST_SITE_COUNT; ++i) if (!have[i]) { Log("a site is underived"); return false; }
    for (unsigned c = 0; c < sizeof(HIST_CALLS) / sizeof(HIST_CALLS[0]); ++c) {
        const HistCall &call = HIST_CALLS[c];
        unsigned target = 0;
        if (!CallTarget(code, codeCount, PinAt[call.pin] + call.offset, &target)) { Log("a call is not a call"); return false; }
        if (target != Sites[call.function]) { Log("a call targets another function"); return false; }
    }
    unsigned phys = SITE(VM_PHYSIOLOGY);
    if (!(SITE(VM_BIRTH) > phys && SITE(VM_BIRTH) < phys + HIST_PHYSIOLOGY_SPAN) ||
        !(SITE(VM_BIRTH_END) > phys && SITE(VM_BIRTH_END) < phys + HIST_PHYSIOLOGY_SPAN)) {
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
typedef int (__thiscall *DoModalFn)(void *dialog, void *scene, int flag);
typedef void (__thiscall *ChangeNameFn)(void *tree, void *villager, const char *name);
typedef bool (__thiscall *GameStateSlotFn)(void *state, int slot);
typedef const char *(__thiscall *MakePathFn)(void *state, int slot);
typedef const char *(__stdcall *GetStringFn)(int id);
typedef void *(__cdecl *SingletonFn)();
typedef bool (__thiscall *ThisBoolFn)(const void *self);

static ImpregnateFn OrigImpregnate;
static ThisVoidFn NextPhysiology;
static TreeVillagerFn NextDeathTimeflow, NextDeathBehavior;
static ThisVoidFn NextCollege, NextBoardingSchool, NextTalentScout;
static UpdateParentsFn NextMarriage;
static ThisVoidFn NextDivorce;
static TreeVillagerBoolFn NextNewFamily, NextLittleVisitor1, NextLittleVisitor2, NextAdoption;
static NextGenerationFn NextNextGeneration;
static DoModalFn NextRandomEvent;
static ChangeNameFn NextRenameMessage, NextRenameSelection;
static ThisVoidFn NextEvict, NextStartOver;
static GameStateSlotFn NextLoad;

static unsigned char *Tree() { return (unsigned char *)SITE(FAMILY_TREE); }
static unsigned char *Manager() { return (unsigned char *)SITE(VILLAGER_MANAGER); }
static unsigned char *GameState() { return *(unsigned char **)SITE(GAME_STATE_INSTANCE); }
static int I32(const unsigned char *p, unsigned off) { return *(const int *)(p + off); }

static unsigned char *Villager(int slot) {
    if (slot < 0 || slot >= (int)HIST_HOUSEHOLD_SLOTS) return 0;
    return Manager() + HIST_VILLAGER_ARRAY_OFFSET + (unsigned)slot * HIST_VILLAGER_STRIDE;
}

static int SlotOf(const void *villager) {
    if (!villager) return -1;
    unsigned off = (unsigned)villager - (unsigned)(Manager() + HIST_VILLAGER_ARRAY_OFFSET);
    if (off % HIST_VILLAGER_STRIDE || off / HIST_VILLAGER_STRIDE >= HIST_HOUSEHOLD_SLOTS) return -1;
    return (int)(off / HIST_VILLAGER_STRIDE);
}

static bool Active(const unsigned char *v) { return v && v[HIST_VILLAGER_ACTIVE] != 0; }

static int Generations() {
    int g = I32(Tree(), HIST_TREE_GENERATIONS_FIELD);
    return g < 0 || g > (int)HIST_TREE_GENERATIONS ? 0 : g;
}

static bool Evicted() { return I32(Tree(), HIST_TREE_EVICTED) != 0; }

static unsigned char *Record(int gen) {
    if (gen <= 0 || gen > (int)HIST_TREE_GENERATIONS) return 0;
    unsigned char *rec = Tree() + (unsigned)gen * HIST_FAMILY_RECORD_SIZE - HIST_FAMILY_RECORD_BASE;
    return rec[0] ? rec : 0;
}

static int RecordChildren(const unsigned char *rec) {
    int n = I32(rec, HIST_RECORD_CHILD_COUNT);
    return n < 0 ? 0 : n > (int)HIST_TREE_CHILDREN ? (int)HIST_TREE_CHILDREN : n;
}

static unsigned char *Peep(unsigned char *rec, int which) {    // 0 parent 1, 1 parent 2, 2.. children
    if (which == 0) return rec + HIST_RECORD_PARENT1;
    if (which == 1) return rec + HIST_RECORD_PARENT2;
    return rec + HIST_RECORD_CHILDREN + (unsigned)(which - 2) * HIST_PEEP_RECORD_SIZE;
}

static bool PeepValid(const unsigned char *peep) { return peep && peep[HIST_PEEP_VALID] != 0; }

static int CurrentSlot() {
    unsigned char *gs = GameState();
    if (!gs) return 0;
    int s = I32(gs, HIST_GAME_STATE_SLOT);
    return s >= 1 && s <= 5 ? s : 0;
}

// The family's name in the log's header: the player's name the save slot carries (Virtual Families 2
// villagers have one name each and the save has no family name; docs/vf2-save-format.md section 4).
static const char *FamilyName() {
    unsigned char *gs = GameState();
    return gs ? (const char *)(gs + HIST_GAME_STATE_NICKNAME) : "";
}

// Translations (vf2tr_b200.dll, loaded after this DLL, so it is looked up when a word is written): the log is a file
// the Family Tree Maker reads back, so it is written in English whatever the game shows. B200Tr_English(id) is the
// line's English, B200Tr_EnglishOf(shown) the English of a translated line the game showed; without that DLL (or a
// translation) both leave the game's own words as they are.
typedef const char *(__cdecl *TrEnglishFn)(int);
typedef const char *(__cdecl *TrEnglishOfFn)(const char *);
static const char *EnglishOfId(unsigned id) {
    HMODULE module = GetModuleHandleW(L"vf2tr_b200.dll");
    TrEnglishFn fn = module ? (TrEnglishFn)GetProcAddress(module, "B200Tr_English") : 0;
    return fn ? fn((int)id) : 0;
}
static const char *EnglishOfShown(const char *shown) {
    HMODULE module = GetModuleHandleW(L"vf2tr_b200.dll");
    TrEnglishOfFn fn = module ? (TrEnglishOfFn)GetProcAddress(module, "B200Tr_EnglishOf") : 0;
    const char *english = fn ? fn(shown) : 0;
    return english ? english : shown;
}

// The executable's own words.
static const char *Word(unsigned id) {
    ((SingletonFn)SITE(SM_GET))();
    const char *s = ((GetStringFn)SITE(SM_GET_STRING))((int)id);
    if (!s || (unsigned)s == SITE(STRING_MISSING)) return "";
    const char *english = EnglishOfId(id);
    return english ? english : s;
}
static const char *SexWord(int sex) { return Word(sex == 1 ? HIST_STR_FEMALE : HIST_STR_MALE); }
static const char *CauseWord(int cause) {
    int id = (int)HIST_STR_CAUSE_UNKNOWN + 1 + cause;      // -1 Unknown causes .. 4 Act of Nature
    if (id < (int)HIST_STR_CAUSE_UNKNOWN || id > (int)HIST_STR_CAUSE_LAST) id = (int)HIST_STR_CAUSE_UNKNOWN;
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
    p.sex = I32(v, HIST_VILLAGER_GENDER);
    p.age = I32(v, HIST_VILLAGER_AGE);
    p.head = I32(v, HIST_VILLAGER_HEAD);
    p.body = I32(v, HIST_VILLAGER_BODY);
    Copy(p.name, v + HIST_VILLAGER_NAME, HIST_VILLAGER_NAME_LEN);
    p.name[HIST_VILLAGER_NAME_LEN] = 0;
}

static unsigned Years(int units) { return units < 0 ? 0u : (unsigned)units / HIST_UNITS_PER_YEAR; }

// Where the villager stands in the current generation's Family Tree record: 0 parent 1, 1 parent 2,
// 2.. a child, -1 not in it. The record's slot is checked with the name, as the game's own records go stale.
static int TreeRole(const Person &p) {
    unsigned char *rec = Record(Generations());
    if (!rec || p.slot < 0) return -1;
    int n = 2 + RecordChildren(rec);
    for (int k = 0; k < n; ++k) {
        unsigned char *peep = Peep(rec, k);
        if (PeepValid(peep) && I32(peep, HIST_PEEP_SLOT) == p.slot && SameText((const char *)peep, p.name, 25))
            return k;
    }
    return -1;
}

static const char *RoleText(int role) {
    return role == 0 ? "Parent" : role == 1 ? "Parent (married in)" : role >= 2 ? "Child" : "(not in the Family Tree)";
}

// ---- the Virtual Villagers patcher's record lines ("  Label: value"), a family member as it writes a villager:
// the name, then (one step further in) the age, sex, head and body. The same writers as vf1logs.dll.
static void Field(Text &t, const char *indent, const char *label, const char *value) {
    t.S(indent).S(label).S(": ").S(value).NL();
}

static void Member(Text &t, const char *indent, const char *label, const Person &p, const char *ageLabel) {
    char deeper[12];
    Text d;
    d.Init(deeper, sizeof(deeper));
    d.S(indent).S("  ");
    t.S(indent).S(label).S(": ").Whole(p.name, HIST_VILLAGER_NAME_LEN).NL();
    if (ageLabel) t.S(deeper).S(ageLabel).S(": ").U(Years(p.age)).NL();
    t.S(deeper).S("Sex: ").S(SexWord(p.sex)).NL();
    t.S(deeper).S("Head: ").I(p.head).NL();
    t.S(deeper).S("Body: ").I(p.body).NL();
}

// A family member at the top of a record: "  Name: ..", "  <age label>: ..", "  Sex: ..", "  Head: ..", "  Body: ..".
static void Self(Text &t, const Person &p, const char *ageLabel) {
    t.S("  Name: ").Whole(p.name, HIST_VILLAGER_NAME_LEN).NL();
    t.S("  ").S(ageLabel).S(": ").U(Years(p.age)).NL();
    t.S("  Sex: ").S(SexWord(p.sex)).NL();
    t.S("  Head: ").I(p.head).NL();
    t.S("  Body: ").I(p.body).NL();
}

// A Family Tree record inside a record (it keeps no age): "  <label>: <name>", Sex, Head, Body one step in.
static void PeepLines(Text &t, const char *label, const unsigned char *peep) {
    t.S("  ").S(label).S(": ").Whole((const char *)peep, 25).NL();
    t.S("    Sex: ").S(SexWord(I32(peep, HIST_PEEP_GENDER))).NL();
    t.S("    Head: ").I(I32(peep, HIST_PEEP_HEAD)).NL().S("    Body: ").I(I32(peep, HIST_PEEP_BODY)).NL();
}

static void Generation(Text &t, int g) { t.S("  Generation: ").I(g).NL(); }

// ================================================================ the Family History files
static char ReadBuffer[0x100000];

// A record's lines and the text appended to the file: heap buffers of kRecordBytes each (every write into them is
// bounded by Text, so a record that would not fit is cut, never written past the buffer). The largest record is
// Evict Family's, every household member's whole name (up to 30 of kNameBoxBytes) on one line.
static const unsigned kRecordBytes = 0x10000;
static char *Line, *Body;

static bool EnsureBuffers() {
    if (!Line) Line = (char *)Alloc(kRecordBytes);
    if (!Body) Body = (char *)Alloc(kRecordBytes);
    return Line && Body;
}

// A record's lines begin: t over Body. False (nothing written) when the buffers could not be made.
static bool Begin(Text &t) {
    if (!EnsureBuffers()) return false;
    t.Init(Body, kRecordBytes);
    return true;
}

static const unsigned kMaxFiles = 4096;

static bool ReadWhole(const char *path, unsigned *got) {
    *got = 0;
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD n = 0;
    BOOL ok = ReadFile(h, ReadBuffer, sizeof(ReadBuffer) - 1, &n, 0);
    CloseHandle(h);
    if (!ok) return false;
    ReadBuffer[n] = 0;
    *got = n;
    return true;
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

// <save folder>\ (from the game's own save path, MakeGameStatePath, theGameState vtable +0Ch).
static bool SaveFolder(char *out, unsigned cap) {
    unsigned char *state = GameState();
    if (!state) return false;
    void **vtable = *(void ***)state;
    const char *save = ((MakePathFn)vtable[HIST_LDW_PATH_VSLOT / 4])(state, 1);
    unsigned n = Length(save);
    if (!save || n == 0 || n + 1 >= MAX_PATH) return false;
    unsigned cut = n;
    while (cut > 0 && save[cut - 1] != '\\' && save[cut - 1] != '/') --cut;
    if (cut == 0 || cut + 1 >= cap) return false;
    Copy(out, save, cut);
    out[cut] = 0;
    return true;
}

// ================================================================ whole names (the slot's Names file)
// The Unicode text DLL's own rule, read the same way (b200names.inc LoadSlot): "VF2 Names 2" (or 1), then one line per short
// form, short<TAB>room<TAB>whole name, in UTF-8; a line that is not a valid short form (ends with "...", at most 24
// bytes stored, fits its room) for a valid name (at least one character, at most kNameBoxBytes bytes stored, no
// control characters) is left out; the first line of a short form in a slot's file counts. Each name is kept in the
// stored form (b200unicode_text.h Encode: the bytes the save would hold), the form every line of the log is in.
struct WholeEntry { unsigned slot, shortLen, wholeLen; char *shortForm, *whole; };
static const unsigned kMaxWhole = 1024;
static WholeEntry Wholes[kMaxWhole];
static unsigned WholeCount;
static bool WholeLoaded[6];

static unsigned FieldLength(const char *s, unsigned max) {
    unsigned n = 0;
    while (s && n < max && s[n]) ++n;
    return n;
}

static bool SameBytes(const char *a, unsigned an, const char *b, unsigned bn) {
    if (an != bn) return false;
    for (unsigned i = 0; i < an; ++i) if (a[i] != b[i]) return false;
    return true;
}

static bool EndsWithMark(const char *s, unsigned n) {
    return n >= 3 && s[n - 1] == '.' && s[n - 2] == '.' && s[n - 3] == '.';
}

// <save folder>\Virtual Families 2 Patcher Data\Names\<the slot's save file>.txt (b200names.inc NamesPath).
static bool NamesPath(int slot, char *out, unsigned cap) {
    unsigned char *state = GameState();
    if (!state || slot < 1 || slot > 5) return false;
    void **vtable = *(void ***)state;
    const char *save = ((MakePathFn)vtable[HIST_LDW_PATH_VSLOT / 4])(state, slot);
    unsigned n = Length(save);
    if (!save || n == 0) return false;
    unsigned cut = n;
    while (cut > 0 && save[cut - 1] != '\\' && save[cut - 1] != '/') --cut;
    static const char middle[] = "Virtual Families 2 Patcher Data\\Names\\";
    unsigned m = sizeof(middle) - 1;
    if (cut == 0 || n + m + 5 >= cap) return false;
    Text t;
    t.Init(out, cap);
    t.Name(save, cut).S(middle).Name(save + cut, n - cut).S(".txt");
    return t.n == n + m + 4;
}

// A whole name the Names file may hold (b200names.inc NameOk).
static bool NameOk(const unsigned *cps, unsigned n, unsigned storedLen) {
    if (!n || storedLen > kNameBoxBytes) return false;
    for (unsigned i = 0; i < n; ++i)
        if (cps[i] < 0x20 || (cps[i] >= 0x7F && cps[i] < 0xA0) || (cps[i] >= 0xD800 && cps[i] <= 0xDFFF)) return false;
    return true;
}

// UTF-8 text -> the stored form (into out, cap bytes): its length, or -1 when it is not valid (b200names.inc FromUtf8).
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

static bool WholeInSlot(unsigned slot, const char *s, unsigned n) {
    for (unsigned i = 0; i < WholeCount; ++i)
        if (Wholes[i].slot == slot && SameBytes(Wholes[i].shortForm, Wholes[i].shortLen, s, n)) return true;
    return false;
}

static bool AddWhole(unsigned slot, const char *s, unsigned sn, const char *w, unsigned wn) {
    if (WholeCount >= kMaxWhole || wn > kNameBoxBytes) return false;
    char *copy = (char *)Alloc(sn + 1 + wn + 1);
    if (!copy) return false;
    WholeEntry &e = Wholes[WholeCount++];
    e.slot = slot; e.shortLen = sn; e.wholeLen = wn; e.shortForm = copy; e.whole = copy + sn + 1;
    Copy(e.shortForm, s, sn);
    e.shortForm[sn] = 0;
    Copy(e.whole, w, wn);
    e.whole[wn] = 0;
    return true;
}

static void ForgetWhole(int slot) {
    unsigned k = 0;
    for (unsigned i = 0; i < WholeCount; ++i) {
        if (slot > 0 && Wholes[i].slot != (unsigned)slot) { Wholes[k++] = Wholes[i]; continue; }
        Release(Wholes[i].shortForm);
    }
    WholeCount = k;
    for (int s = 1; s <= 5; ++s) if (slot <= 0 || s == slot) WholeLoaded[s] = false;
}

static void LoadWhole(int slot) {
    char path[MAX_PATH + 64];
    if (slot < 1 || slot > 5 || !NamesPath(slot, path, sizeof(path))) return;
    WholeLoaded[slot] = true;
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD size = GetFileSize(h, 0), got = 0;
    unsigned char *text = size && size < (4u << 20) ? (unsigned char *)Alloc(size + 1) : 0;
    bool ok = text && ReadFile(h, text, size, &got, 0) && got == size;
    CloseHandle(h);
    if (!ok) { Release(text); return; }
    unsigned at = 0;
    int version = nf::Header(text, size, &at);
    if (!version) { Release(text); return; }
    static unsigned char shortForm[64], whole[kNameBoxBytes + 8];
    while (at < size) {
        unsigned end = at;
        while (end < size && text[end] != '\n') ++end;
        unsigned stop = end > at && text[end - 1] == '\r' ? end - 1 : end;
        unsigned tab1, tab2, body, room;
        // a record cut short, merged with another or with a wrong checksum is skipped (b200names_file.h)
        if (nf::Split(text, at, stop, version, &tab1, &tab2, &body, &room) && room >= 1 &&
            room < kNameBoxBytes) {
            int sn = FromUtf8(text + at, tab1 - at, shortForm, room < sizeof(shortForm) ? room : 0, false);
            int wn = FromUtf8(text + tab2 + 1, body - tab2 - 1, whole, kNameBoxBytes, true);
            if (sn > 0 && wn > 0 && sn <= 24 && EndsWithMark((const char *)shortForm, (unsigned)sn) &&
                !WholeInSlot((unsigned)slot, (const char *)shortForm, (unsigned)sn))
                AddWhole((unsigned)slot, (const char *)shortForm, (unsigned)sn, (const char *)whole, (unsigned)wn);
        }
        at = end + 1;
    }
    Release(text);
}

static void EnsureWhole() {
    for (int s = 1; s <= 5; ++s) if (!WholeLoaded[s]) LoadWhole(s);
}

// The entry whose short form is s (n bytes): the current slot's first, else any slot's (b200names.inc FindShort).
static int FindWhole(const char *s, unsigned n) {
    int any = -1;
    unsigned prefer = (unsigned)CurrentSlot();
    for (unsigned i = 0; i < WholeCount; ++i)
        if (SameBytes(Wholes[i].shortForm, Wholes[i].shortLen, s, n)) {
            if (Wholes[i].slot == prefer) return (int)i;
            if (any < 0) any = (int)i;
        }
    return any;
}

static const char *WholeName(const char *stored, unsigned max) {
    unsigned n = FieldLength(stored, max);
    if (!EndsWithMark(stored, n)) return 0;
    EnsureWhole();
    int e = FindWhole(stored, n);
    if (e < 0) {                       // not known yet: the Unicode text DLL may have written it since
        int slot = CurrentSlot();
        if (slot) { ForgetWhole(slot); LoadWhole(slot); e = FindWhole(stored, n); }
    }
    return e < 0 ? 0 : Wholes[e].whole;
}

static const char kSaves[] = "Virtual Families 2 Patcher\\Save ";

// <save folder>\Virtual Families 2 Patcher\Save <slot>
static bool SlotRoot(int slot, Text &t) {
    char folder[MAX_PATH];
    if (slot < 1 || slot > 5 || !SaveFolder(folder, sizeof(folder))) return false;
    t.S(folder).S(kSaves).U((unsigned)slot);
    return t.n + 120 < t.cap;
}

// ...\Logs\Family History\Family History <k>.txt
static bool HistoryFile(int slot, unsigned number, char *out, unsigned cap) {
    Text t;
    t.Init(out, cap);
    if (!SlotRoot(slot, t)) return false;
    t.S("\\Logs\\Family History\\Family History ").U(number).S(".txt");
    return t.n + 8 < cap;
}

// "Family: <name> (Save <N>)" -- the header every file opens with (the Virtual Villagers logs'
// "Village: <name> (Save <S>)").
static void Header(Text &t, int slot) {
    const char *name = FamilyName();
    t.S("Family: ");
    if (name[0]) t.Whole(name, HIST_GAME_STATE_NICKNAME_LEN - 1); else t.S("(no name)");
    t.S(" (Save ").U((unsigned)slot).S(")").NL();
}

// The records of the text: their heading lines start with "[" (the dated and backfilled ones).
static unsigned CountRecords(const char *text, unsigned len) {
    unsigned count = 0;
    for (unsigned i = 0; i < len; ++i)
        if ((i == 0 || text[i - 1] == '\n') && text[i] == '[') ++count;
    return count;
}

// The newest file's number (0 when there is none) and how many records it holds.
static unsigned NewestFile(int slot, unsigned *records) {
    char path[MAX_PATH + 64];
    unsigned newest = 0;
    *records = 0;
    for (unsigned k = 1; k <= kMaxFiles; ++k) {
        if (!HistoryFile(slot, k, path, sizeof(path)) || !Exists(path)) break;
        newest = k;
    }
    unsigned got = 0;
    if (newest && HistoryFile(slot, newest, path, sizeof(path)) && ReadWhole(path, &got))
        *records = CountRecords(ReadBuffer, got);
    return newest;
}

// The first file, with its header, when the slot has none.
static void CreateLog(int slot) {
    char path[MAX_PATH + 64];
    unsigned records = 0;
    if (NewestFile(slot, &records) || !HistoryFile(slot, 1, path, sizeof(path)) || !EnsureBuffers()) return;
    Text t;
    t.Init(Line, kRecordBytes);
    Header(t, slot);
    Append(path, Line, t.n);
}

// The highest number of a record kind ("Birth" in "[...] Birth 12") in every file of the slot's log: the next
// record of that kind gets the number after it.
static unsigned NextNumber(int slot, const char *kind) {
    char path[MAX_PATH + 64];
    unsigned highest = 0, m = Length(kind);
    for (unsigned k = 1; k <= kMaxFiles && HistoryFile(slot, k, path, sizeof(path)) && Exists(path); ++k) {
        unsigned got = 0;
        if (!ReadWhole(path, &got)) continue;
        for (unsigned i = 0; i < got; ++i) {
            if ((i && ReadBuffer[i - 1] != '\n') || ReadBuffer[i] != '[') continue;
            unsigned j = i;
            while (j < got && ReadBuffer[j] != ']' && ReadBuffer[j] != '\n') ++j;
            j += 2;
            if (j + m + 1 > got || !StartsWith(ReadBuffer + j, kind) || ReadBuffer[j + m] != ' ') continue;
            unsigned v = 0;
            for (j += m + 1; j < got && ReadBuffer[j] >= '0' && ReadBuffer[j] <= '9' && v < 100000000u; ++j)
                v = v * 10 + (unsigned)(ReadBuffer[j] - '0');
            if (v > highest && (j >= got || ReadBuffer[j] == '\r' || ReadBuffer[j] == '\n')) highest = v;
        }
    }
    return highest + 1;
}

// One record, written now: the heading "[YYYY-MM-DD HH:MM:SS] <kind> <n>" (numbered per kind, as the Virtual
// Villagers logs number theirs) and its "  Label: value" lines, then a blank line; appended to the newest file, or
// to a new numbered file when the newest holds 2000 records.
static void WriteNow(int slot, const char *kind, const char *lines, bool backfilled) {
    char path[MAX_PATH + 64];
    if (slot < 1) return;
    unsigned number = NextNumber(slot, kind);
    unsigned records = 0;
    unsigned newest = NewestFile(slot, &records);
    unsigned file = !newest ? 1 : records >= HIST_HISTORY_RECORDS_PER_FILE ? newest + 1 : newest;
    if (!HistoryFile(slot, file, path, sizeof(path)) || !EnsureBuffers()) return;
    Text t;
    t.Init(Line, kRecordBytes);
    if (!Exists(path)) Header(t, slot);
    if (backfilled) {
        t.S("[backfilled, no date] ");
    } else {
        SYSTEMTIME now;
        GetLocalTime(&now);
        t.S("[").U(now.wYear).S("-").Two(now.wMonth).S("-").Two(now.wDay).S(" ").Two(now.wHour).S(":")
            .Two(now.wMinute).S(":").Two(now.wSecond).S("] ");
    }
    t.S(kind).S(" ").U(number).NL().S(lines).NL();
    if (Append(path, Line, t.n)) ++B200History_Status.records;
}

// While a Random Event's dialog is open, the records its choice makes (a child who arrives or leaves home) wait,
// and follow the event's own record, as vf1logs.dll orders them.
struct Pending { int slot; char kind[24]; char *lines; };    // lines: a heap buffer of kRecordBytes, made once
static Pending Waiting[8];
static unsigned WaitingCount;
static int gInEvent;
static char gEventTitle[256];          // the open Random Event's title, as the player sees it
static const char *gEventKind = "Popup Event";

static void Write(int slot, const char *kind, const char *lines, bool backfilled = false) {
    if (gInEvent && !backfilled && WaitingCount < sizeof(Waiting) / sizeof(Waiting[0])) {
        Pending &w = Waiting[WaitingCount];
        if (!w.lines) w.lines = (char *)Alloc(kRecordBytes);
        if (w.lines) {
            ++WaitingCount;
            w.slot = slot;
            Text k, l;
            k.Init(w.kind, sizeof(w.kind));
            k.S(kind);
            l.Init(w.lines, kRecordBytes);
            l.S(lines);
            return;
        }
    }
    WriteNow(slot, kind, lines, backfilled);
}

static void FlushWaiting() {
    for (unsigned i = 0; i < WaitingCount; ++i) WriteNow(Waiting[i].slot, Waiting[i].kind, Waiting[i].lines, false);
    WaitingCount = 0;
}

// ---- remarriage: the spouse a person married before in the same generation and why they left ("died" or
// "divorced"), from this slot's own Family History (the save forgets a spouse who left or died before any child,
// and a remarriage overwrites the record's second parent). Records after the last eviction only.
// The names in the log are whole (or, in a log written before whole names, short forms), in UTF-8 (a log an
// earlier build wrote holds the stored form: read per sequence, the same text). `head` (the save's stored name) is
// compared as its whole name in UTF-8. earlier gets the whole name as the log wrote it, in UTF-8 (kNameBytes room: a stored
// byte is at most three UTF-8 bytes).
static const unsigned kNameBytes = 3 * kNameBoxBytes + 1;
static char EarlierA[kNameBytes], EarlierB[kNameBytes], EarlierHead[kNameBytes], ValueRaw[kNameBytes];

static bool Value(const char *p, const char *label, char *out, unsigned cap) {   // "  <label>: <value>", in UTF-8
    if (!StartsWith(p, label)) return false;
    p += Length(label);
    unsigned k = 0;
    while (*p && *p != '\r' && *p != '\n') { if (k + 1 < kNameBytes) ValueRaw[k++] = *p; ++p; }
    ValueRaw[k] = 0;
    Text t;
    t.Init(out, cap);
    t.Utf8(ValueRaw, k);
    return true;
}

static bool EarlierSpouse(int slot, int gen, const char *stored, char *earlier, char *how) {
    char path[MAX_PATH + 64];
    earlier[0] = how[0] = 0;
    Text h;
    h.Init(EarlierHead, kNameBytes);
    h.Whole(stored, 25);
    const char *head = EarlierHead;
    char kind[16], g[12];
    char *a = EarlierA, *b = EarlierB;
    kind[0] = a[0] = b[0] = g[0] = 0;
    for (unsigned k = 1; k <= kMaxFiles && HistoryFile(slot, k, path, sizeof(path)) && Exists(path); ++k) {
        unsigned got = 0;
        if (!ReadWhole(path, &got)) continue;
        for (const char *p = ReadBuffer;; ) {
            bool heading = *p == '[' || *p == 0;
            if (heading && kind[0]) {                  // the record before ends: what it says
                int gn = 0;
                for (const char *q = g; *q >= '0' && *q <= '9'; ++q) gn = gn * 10 + (*q - '0');
                if (SameText(kind, "Marriage", 16) && gn == gen && (SameText(a, head, kNameBytes) || SameText(b, head, kNameBytes))) {
                    Copy(earlier, SameText(a, head, kNameBytes) ? b : a, kNameBytes);
                    how[0] = 0;
                } else if (SameText(kind, "Death", 16) && earlier[0] && SameText(a, earlier, kNameBytes)) {
                    Copy(how, "died", 5);
                } else if (SameText(kind, "Divorce", 16) && earlier[0] && SameText(b, earlier, kNameBytes)) {
                    Copy(how, "divorced", 9);
                } else if (SameText(kind, "Evict Family", 16)) {
                    earlier[0] = how[0] = 0;
                }
                kind[0] = a[0] = b[0] = g[0] = 0;
            }
            if (!*p) break;
            if (*p == '[') {
                const char *q = p;
                while (*q && *q != ']') ++q;
                if (*q) q += 2;
                unsigned n = 0;
                while (*q && *q != '\r' && *q != '\n' && !(*q == ' ' && q[1] >= '0' && q[1] <= '9') && n < 15) kind[n++] = *q++;
                kind[n] = 0;
            } else {
                Value(p, "  Family member: ", a, kNameBytes) || Value(p, "  Name: ", a, kNameBytes) ||
                    Value(p, "  Married: ", b, kNameBytes) || Value(p, "  Divorced: ", b, kNameBytes) ||
                    Value(p, "  Generation: ", g, sizeof(g));
            }
            while (*p && *p != '\n') ++p;
            if (*p) ++p;
        }
    }
    return earlier[0] != 0;
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
static Logged DeathLogged[HIST_HOUSEHOLD_SLOTS];

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

// ---- conception: the father kept per mother for her births this session
struct Conceived { int valid; char mother[28]; Person father; };
static Conceived Fathers[HIST_HOUSEHOLD_SLOTS];

static void ClearSession() {
    Zero(DeathLogged, sizeof(DeathLogged));
    Zero(Fathers, sizeof(Fathers));
}

static void WipeSlot(int slot) {
    char path[MAX_PATH + 64];
    Text t;
    t.Init(path, sizeof(path));
    if (!SlotRoot(slot, t)) return;
    DeleteTree(path, t.n, sizeof(path), true);
    ClearSession();
    ++B200History_Status.wipes;
}

// ================================================================ the events
static int gInLoad;
static int gStartedOver;      // the confirmed Start Over: the next new family's log says so

// ---- conception (the babies expected: one, twins or triplets)
// The father: the household villager whose head and body are the ones Impregnate was given (both of its callers
// pass the father's own), the mother's spouse in the Family Tree first.
static unsigned char *FindFather(const unsigned char *mother, int head, int body) {
    unsigned char *rec = Record(Generations());
    int ms = SlotOf(mother);
    if (rec) {
        for (int k = 0; k < 2; ++k) {
            unsigned char *peep = Peep(rec, k);
            int s = I32(peep, HIST_PEEP_SLOT);
            if (!PeepValid(peep) || s == ms) continue;
            unsigned char *v = Villager(s);
            if (Active(v) && I32(v, HIST_VILLAGER_HEAD) == head && I32(v, HIST_VILLAGER_BODY) == body) return v;
        }
    }
    for (int s = 0; s < (int)HIST_HOUSEHOLD_SLOTS; ++s) {
        unsigned char *v = Villager(s);
        if (s == ms || !Active(v) || I32(v, HIST_VILLAGER_HEALTH) <= 0) continue;
        if (I32(v, HIST_VILLAGER_HEAD) == head && I32(v, HIST_VILLAGER_BODY) == body) return v;
    }
    return 0;
}

static void OnConception(const unsigned char *mother, const unsigned char *father) {
    int slot = CurrentSlot();
    if (!slot) return;
    Person m, f;
    Capture(mother, m);
    Capture(father, f);
    if (m.slot >= 0) {
        Conceived &c = Fathers[m.slot];
        c.valid = father != 0;
        Copy(c.mother, m.name, 28);
        c.father = f;
    }
    Text t;
    if (!Begin(t)) return;
    Member(t, "  ", "Mother", m, "Age at conception");
    if (father) Member(t, "  ", "Father", f, "Age at conception");
    else Field(t, "  ", "Father", "(unknown)");
    t.S("  Babies ").S(Word(HIST_STR_NURSING)).S(": ").I(I32(mother, HIST_VILLAGER_CARRIED)).NL();
    Generation(t, Generations());
    Write(slot, "Conception", Body);
}

// ---- births: what the physiology pass delivered (single, twins, triplets)
struct PassState {
    int reserved[3];
    int pregnant[HIST_HOUSEHOLD_SLOTS];
    unsigned char present[HIST_HOUSEHOLD_SLOTS];
};
static PassState Before;

static void SnapshotPass(PassState &s) {
    const unsigned char *gs = GameState();
    for (int k = 0; k < 3; ++k) s.reserved[k] = gs ? I32(gs, HIST_GAME_STATE_RESERVED_BABY + 4u * (unsigned)k) : -1;
    for (int i = 0; i < (int)HIST_HOUSEHOLD_SLOTS; ++i) {
        const unsigned char *v = Villager(i);
        s.pregnant[i] = I32(v, HIST_VILLAGER_PREGNANT);
        s.present[i] = v[HIST_VILLAGER_ACTIVE];
    }
}

// The father: the one this session saw at the conception, else the current generation's other parent whose
// head and body are the ones the game kept at conception (Impregnate stores the head and body it is given, the
// father's, at +6AF0h / +6AECh; the name it is given is the constant "Joey"). False when neither is known.
static bool Father(const Person &mother, Person &out) {
    Zero(&out, sizeof(out));
    if (mother.slot >= 0 && Fathers[mother.slot].valid && SameText(Fathers[mother.slot].mother, mother.name, 28)) {
        out = Fathers[mother.slot].father;
        return true;
    }
    unsigned char *rec = Record(Generations());
    const unsigned char *m = Villager(mother.slot);
    if (!rec || !m) return false;
    for (int k = 0; k < 2; ++k) {
        unsigned char *peep = Peep(rec, k);
        unsigned char *other = Peep(rec, 1 - k);
        if (!PeepValid(peep) || !SameText((const char *)peep, mother.name, 25) || !PeepValid(other)) continue;
        if (I32(other, HIST_PEEP_HEAD) != I32(m, HIST_VILLAGER_FATHER_HEAD) ||
            I32(other, HIST_PEEP_BODY) != I32(m, HIST_VILLAGER_FATHER_BODY)) return false;
        Copy(out.name, other, 25);
        out.sex = I32(other, HIST_PEEP_GENDER);
        out.head = I32(other, HIST_PEEP_HEAD);
        out.body = I32(other, HIST_PEEP_BODY);
        return true;
    }
    return false;
}

static void OnBirths(int mother) {
    int slot = CurrentSlot();
    const unsigned char *gs = GameState();
    if (!slot || !gs) return;
    int born[3], n = 0;
    for (int k = 0; k < 3; ++k) {
        int b = Before.reserved[k];
        if (b < 0 || b >= (int)HIST_HOUSEHOLD_SLOTS || b == mother) continue;
        if (I32(gs, HIST_GAME_STATE_RESERVED_BABY + 4u * (unsigned)k) != -1) continue;
        if (Before.present[b] || !Active(Villager(b))) continue;
        born[n++] = b;
    }
    if (!n) return;
    Person m, f;
    Capture(Villager(mother), m);
    bool known = Father(m, f);
    if (m.slot >= 0) Fathers[m.slot].valid = 0;
    for (int i = 0; i < n; ++i) {
        Person c;
        Capture(Villager(born[i]), c);
        Text t;
        if (!Begin(t)) return;
        t.S("  Child: ").Whole(c.name, 25).NL();
        t.S("    Sex: ").S(SexWord(c.sex)).NL().S("    Head: ").I(c.head).NL().S("    Body: ").I(c.body).NL();
        t.S("  Mother: ").Whole(m.name, 25).NL().S("    Head: ").I(m.head).NL().S("    Body: ").I(m.body).NL();
        if (known) t.S("  Father: ").Whole(f.name, 25).NL().S("    Head: ").I(f.head).NL().S("    Body: ").I(f.body).NL();
        else Field(t, "  ", "Father", "(unknown)");
        Field(t, "  ", "Born as", n == 1 ? "Single birth" : n == 2 ? "Twin" : "Triplet");
        Generation(t, Generations());
        Write(slot, "Birth", Body);
    }
}

// ---- deaths (both callers deactivate the villager right after reporting it, so each death is reported once)
static void ReportDeath(TreeVillagerFn next, void *tree, void *villager) {
    const unsigned char *v = (const unsigned char *)villager;
    Person p;
    Capture(v, p);
    bool dead = v && I32(v, HIST_VILLAGER_HEALTH) <= 0;
    int cause = v ? I32(v, HIST_VILLAGER_CAUSE) : -1;
    int role = TreeRole(p);
    int gen = Generations();
    char widowed[28];
    widowed[0] = 0;
    if (dead && (role == 0 || role == 1)) {            // the other parent, alive, is left with no spouse
        unsigned char *rec = Record(gen);
        unsigned char *other = rec ? Peep(rec, 1 - role) : 0;
        if (PeepValid(other) && I32(other, HIST_PEEP_SLOT) != -1) {
            Copy(widowed, other, 25);
            widowed[25] = 0;
        }
    }
    next(tree, villager);
    int slot = CurrentSlot();
    if (!dead || p.slot < 0 || !slot || gInLoad || WasLogged(p)) return;
    MarkLogged(p);
    Text t;
    if (!Begin(t)) return;
    t.S("  Name: ").Whole(p.name, 25).NL();
    t.S("  Age at death: ").U(Years(p.age)).NL();
    t.S("  Sex: ").S(SexWord(p.sex)).NL();
    Field(t, "  ", "Cause of death", CauseWord(cause));
    t.S("  Head: ").I(p.head).NL().S("  Body: ").I(p.body).NL();
    Field(t, "  ", "Family role", RoleText(role));
    Generation(t, gen);
    if (widowed[0]) t.S("  Current spouse of ").Whole(widowed, 25).S(": (none)").NL();
    Write(slot, "Death", Body);
}

// ---- marriage and remarriage (UpdateParents: the one it writes into the record's second parent married in;
// either sex, the patcher's same-sex marriage included)
static void OnMarriage(const Person &head, const Person &spouse, int gen) {
    int slot = CurrentSlot();
    if (!slot) return;
    static char earlier[kNameBytes];
    char how[12];
    bool again = EarlierSpouse(slot, gen, head.name, earlier, how);
    Text t;
    if (!Begin(t)) return;
    Member(t, "  ", "Family member", head, "Age");
    Member(t, "  ", "Married", spouse, "Age");
    if (again) {
        t.S("  Remarried: yes").NL().S("  Earlier spouse: ").Utf8(earlier, kNameBytes);
        if (how[0]) t.S(" (").S(how).S(")");
        t.NL();
    }
    t.S("  Current spouse of ").Whole(head.name, 25).S(": ").Whole(spouse.name, 25).NL();
    Generation(t, gen);
    Write(slot, "Marriage", Body);
}

// ---- divorce (the patcher's Divorce Spouse): before the spouse leaves, the record still holds the generation's
// other parent
static void OnDivorce(const unsigned char *spouseVillager) {
    int slot = CurrentSlot();
    if (!slot) return;
    Person p;
    Capture(spouseVillager, p);
    unsigned char *rec = Record(Generations());
    unsigned char *head = rec ? Peep(rec, 0) : 0;
    bool known = PeepValid(head);
    Text t;
    if (!Begin(t)) return;
    if (known) PeepLines(t, "Family member", head); else Field(t, "  ", "Family member", "(unknown)");
    Member(t, "  ", "Divorced", p, "Age");
    Field(t, "  ", "How", "Divorce Spouse");
    if (known) t.S("  Current spouse of ").Whole((const char *)head, 25).S(": (none)").NL();
    Generation(t, Generations());
    Write(slot, "Divorce", Body);
}

// ---- a family member who joined the family from outside (VV's "Arrived")
static void OnArrived(const unsigned char *v, const char *how) {
    int slot = CurrentSlot();
    if (!slot || !v) return;
    Person c;
    Capture(v, c);
    Text t;
    if (!Begin(t)) return;
    Self(t, c, "Age at arrival");
    Field(t, "  ", "How", how);
    Field(t, "  ", "Family role", RoleText(TreeRole(c)));
    Generation(t, Generations());
    Write(slot, "Arrived", Body);
}

// ---- a generation begins: a new family, Next Generation (the heir chosen)
static void OnGeneration(const unsigned char *v, bool newFamily, bool afterEviction) {
    int slot = CurrentSlot();
    if (!slot || !v) return;
    Person p;
    Capture(v, p);
    const char *how;
    if (newFamily && afterEviction) {
        how = "Founder (after the eviction)";
    } else if (newFamily) {
        // A brand-new family in this slot (a new game, or after Start Over): the folder is the new family's.
        WipeSlot(slot);
        CreateLog(slot);
        if (gStartedOver) Write(slot, "Start Over", "  The earlier family's history was cleared.\r\n");
        how = "Founder (adopted and started the family)";
    } else {
        how = "Heir (inherited the house)";
    }
    if (newFamily) gStartedOver = 0;
    Text t;
    if (!Begin(t)) return;
    Self(t, p, "Age");
    Field(t, "  ", "How", how);
    Generation(t, Generations());
    Write(slot, newFamily ? "Generation" : Word(HIST_STR_NEW_GENERATION), Body);
}

// ---- leaving home: college (the game's own picture caption, "{name} is going to college!"), The Talent Scout,
// Boarding School
enum { LEFT_COLLEGE = 0, LEFT_BOARDING_SCHOOL = 1, LEFT_TALENT_SCOUT = 2 };

static void OnLeftHome(const unsigned char *v, int why) {
    int slot = CurrentSlot();
    if (!slot || !v) return;
    Person p;
    Capture(v, p);
    Text t;
    if (!Begin(t)) return;
    Self(t, p, "Age");
    t.S("  What happened: ");
    if (why == LEFT_COLLEGE) {
        for (const char *s = Word(HIST_STR_COLLEGE_TITLE); *s;) {
            if (StartsWith(s, "{name}")) { t.Whole(p.name, 25); s += 6; }
            else { char c[2] = { *s++, 0 }; t.S(c); }
        }
    } else if (why == LEFT_TALENT_SCOUT) {
        t.S("Left home with ").Utf8(gInEvent ? gEventTitle : Word(HIST_STR_TALENT_SCOUT), 200).S(" (").S(gEventKind).S(")");
    } else {
        t.S("Sent to Boarding School");
    }
    t.NL();
    Generation(t, Generations());
    Write(slot, "Left Home", Body);
}

// ---- a rename in the Details box (the game calls ChangeName whenever the box closes or the selection changes;
// a record only when the name really changes)
static void OnRename(const Person &p, const char *name) {
    int slot = CurrentSlot();
    if (!slot || p.slot < 0) return;
    Text t;
    if (!Begin(t)) return;
    t.S("  Old name: ").Whole(p.name, 25).NL();
    t.S("  New name: ").Whole(name, 24).NL();
    t.S("  Age: ").U(Years(p.age)).NL();
    t.S("  Sex: ").S(SexWord(p.sex)).NL();
    t.S("  Head: ").I(p.head).NL();
    t.S("  Body: ").I(p.body).NL();
    Generation(t, Generations());
    Write(slot, "Renamed", Body);
}

// ---- a Random Event: an Email Event when the event is an e-mail (its vtable +14h, which FireEvent's own scan and
// the dialog's draw ask), else a Popup Event; the title as the dialog draws it (+54h); the choice (+830h, 0 A, 1 B)
// on an event with choices (vtable +10h), as CIslandEventDialog::HandleMessage keeps it.
static void EventRecord(int slot, const char *kind, const char *title, int choice) {
    Text t;
    if (!Begin(t)) return;
    t.S("  ").S(kind).S(": ").Utf8(title, 200).NL();
    if (choice >= 0) t.S("  Choice: ").S(choice ? "B" : "A").NL();
    Generation(t, Generations());
    Write(slot, "Random Event", Body);
}

// ---- Evict Family: the household is sent away and the Family Tree starts again
static void OnEvict() {
    int slot = CurrentSlot();
    if (!slot) return;
    Text t;
    if (!Begin(t)) return;
    t.S("  Family members:");
    bool any = false;
    for (int s = 0; s < (int)HIST_HOUSEHOLD_SLOTS; ++s) {
        unsigned char *v = Villager(s);
        if (!Active(v) || I32(v, HIST_VILLAGER_HEALTH) <= 0) continue;
        t.S(any ? ", " : " ").Whole((const char *)(v + HIST_VILLAGER_NAME), HIST_VILLAGER_NAME_LEN);
        any = true;
    }
    if (!any) t.S(" (none)");
    t.NL();
    Generation(t, Generations());
    Write(slot, "Evict Family", Body);
}

// ================================================================ an existing family's first log
// What the save's Family Tree holds, once, when the slot's log has no records yet: one record per generation, its
// parents, its children (a slot of -1: "Died: yes") and the newest generation's current spouse. Nothing the tree
// does not hold (no dates, ages, causes, twins or earlier spouses).
static void BackfillPeep(Text &t, const char *label, const unsigned char *peep) {
    PeepLines(t, label, peep);
    if (I32(peep, HIST_PEEP_SLOT) == -1) t.S("    Died: yes").NL();
}

static void Backfill(int slot) {
    int gens = Generations();
    for (int g = 1; g <= gens; ++g) {
        unsigned char *rec = Record(g);
        if (!rec) continue;
        unsigned char *p1 = Peep(rec, 0), *p2 = Peep(rec, 1);
        bool v1 = PeepValid(p1), v2 = PeepValid(p2);
        Text t;
        if (!Begin(t)) return;
        if (v1) BackfillPeep(t, "Parent", p1);
        if (v2) BackfillPeep(t, "Parent (married in)", p2);
        int n = RecordChildren(rec);
        for (int c = 0; c < n; ++c)
            if (PeepValid(Peep(rec, 2 + c))) BackfillPeep(t, "Child", Peep(rec, 2 + c));
        if (g == gens && v1 && v2 && I32(p1, HIST_PEEP_SLOT) != -1 && I32(p2, HIST_PEEP_SLOT) != -1)
            t.S("  Current spouse of ").Whole((const char *)p1, 25).S(": ").Whole((const char *)p2, 25).NL();
        Generation(t, g);
        t.S("  Note: Recorded afterwards (from the save's Family Tree: no dates, ages, causes, twins or earlier spouses)")
            .NL();
        Write(slot, "Family Tree", Body, true);
    }
}

static void OnLoaded(int slot) {
    ClearSession();
    gStartedOver = 0;
    if (Generations() <= 0) return;        // no family: the new family's adoption starts the log
    CreateLog(slot);
    B200History_Status.lastLoad = 1;
    char path[MAX_PATH + 64];
    for (unsigned k = 1; HistoryFile(slot, k, path, sizeof(path)) && Exists(path); ++k) {
        unsigned got = 0;
        if (ReadWhole(path, &got) && CountRecords(ReadBuffer, got)) return;   // never backfilled twice
    }
    Backfill(slot);
    B200History_Status.lastLoad = 2;
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
    for (int i = 0; i < (int)HIST_HOUSEHOLD_SLOTS; ++i)
        if (Before.pregnant[i] && !I32(Villager(i), HIST_VILLAGER_PREGNANT)) OnBirths(i);
}

static void __fastcall DeathTimeflowHook(void *tree, void *, void *villager) { ReportDeath(NextDeathTimeflow, tree, villager); }
static void __fastcall DeathBehaviorHook(void *tree, void *, void *villager) { ReportDeath(NextDeathBehavior, tree, villager); }

static void LeftHome(ThisVoidFn next, void *villager, int why) {
    bool was = ((unsigned char *)villager)[HIST_VILLAGER_LEFT_HOME] != 0;
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
    unsigned char *rec = Record(Generations());
    if (ok && !gInLoad && rec) {
        // The one who married in is the one UpdateParents wrote into the record's second parent; either sex.
        unsigned char *spouse = Peep(rec, 1);
        bool bIn = I32(spouse, HIST_PEEP_SLOT) == pb.slot && SameText((const char *)spouse, pb.name, 25);
        if (bIn) OnMarriage(pa, pb, Generations()); else OnMarriage(pb, pa, Generations());
    }
    return ok;
}

static void __fastcall DivorceHook(void *spouse, void *) {
    if (!gInLoad) OnDivorce((const unsigned char *)spouse);
    NextDivorce(spouse);
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

// A child who joins: The Little Visitor (inside its Popup Event: "Adopted (Popup Event: The Little Visitor)") and
// Adoption Services ("Adopted (Adoption Services)").
static bool Joined(TreeVillagerBoolFn next, void *tree, void *villager, unsigned title) {
    bool ok = next(tree, villager);
    if (ok && !gInLoad) {
        char how[300];
        Text h;
        h.Init(how, sizeof(how));
        h.S("Adopted (");
        if (gInEvent) h.S(gEventKind).S(": ").Utf8(gEventTitle, 200); else h.S(Word(title));
        h.S(")");
        OnArrived((const unsigned char *)villager, how);
    }
    return ok;
}
static bool __fastcall LittleVisitor1Hook(void *tree, void *, void *v) { return Joined(NextLittleVisitor1, tree, v, HIST_STR_LITTLE_VISITOR); }
static bool __fastcall LittleVisitor2Hook(void *tree, void *, void *v) { return Joined(NextLittleVisitor2, tree, v, HIST_STR_LITTLE_VISITOR); }
static bool __fastcall AdoptionHook(void *tree, void *, void *v) { return Joined(NextAdoption, tree, v, HIST_STR_ADOPTION); }

// A Random Event's dialog, shown: its kind and title now, its record after the player's choice, then the records
// the choice made.
static int __fastcall RandomEventHook(void *dialog, void *, void *scene, int flag) {
    const unsigned char *d = (const unsigned char *)dialog;
    const void *event = *(const void *const *)(d + HIST_DIALOG_EVENT);
    const char *title = *(const char *const *)(d + HIST_DIALOG_TITLE);
    if (title && title[0] && (unsigned)title != SITE(STRING_MISSING)) title = EnglishOfShown(title);
    Text t;
    t.Init(gEventTitle, sizeof(gEventTitle));
    if (title && title[0] && (unsigned)title != SITE(STRING_MISSING)) t.Name(title, sizeof(gEventTitle) - 1);
    else t.S("(no title)");
    bool email = event && ((ThisBoolFn)(*(void *const *const *)event)[HIST_EVENT_IS_EMAIL_VSLOT / 4])(event);
    bool choices = event && ((ThisBoolFn)(*(void *const *const *)event)[HIST_EVENT_HAS_CHOICES_VSLOT / 4])(event);
    gEventKind = email ? "Email Event" : "Popup Event";
    WaitingCount = 0;
    ++gInEvent;
    int result = NextRandomEvent(dialog, scene, flag);
    --gInEvent;
    int slot = CurrentSlot();
    if (slot && !gInLoad) EventRecord(slot, gEventKind, gEventTitle, choices ? I32(d, HIST_DIALOG_CHOICE) : -1);
    FlushWaiting();
    return result;
}

static void Rename(ChangeNameFn next, void *tree, void *villager, const char *name) {
    Person p;
    Capture((const unsigned char *)villager, p);
    next(tree, villager, name);
    if (!gInLoad && name && name[0] && !SameText(p.name, name, 25)) OnRename(p, name);
}
static void __fastcall RenameMessageHook(void *tree, void *, void *v, const char *name) { Rename(NextRenameMessage, tree, v, name); }
static void __fastcall RenameSelectionHook(void *tree, void *, void *v, const char *name) { Rename(NextRenameSelection, tree, v, name); }

// Evict Family keeps the slot's log: everything before the "Evict Family" record belongs to the family that left
// (written before the household is removed), and the next family's first generation is "after the eviction".
static void __fastcall EvictHook(void *tree, void *) {
    if (!gInLoad) OnEvict();
    NextEvict(tree);
}

// Start Over: the slot's folder is the next family's alone (Backups kept); the next family's log opens with the
// Start Over.
static void __fastcall StartOverHook(void *state, void *) {
    int slot = CurrentSlot();
    if (slot) WipeSlot(slot);
    gStartedOver = 1;
    NextStartOver(state);
}

static bool __fastcall LoadHook(void *state, void *, int slot) {
    ++gInLoad;
    bool ok = NextLoad(state, slot);
    --gInLoad;
    if (ok && slot >= 1 && slot <= 5) OnLoaded(slot);
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
    case HIST_SITE_CALL_PHYSIOLOGY: return (void *)&PhysiologyHook;
    case HIST_SITE_CALL_DEATH_TIMEFLOW: return (void *)&DeathTimeflowHook;
    case HIST_SITE_CALL_DEATH_BEHAVIOR: return (void *)&DeathBehaviorHook;
    case HIST_SITE_CALL_COLLEGE: return (void *)&CollegeHook;
    case HIST_SITE_CALL_BOARDING_SCHOOL: return (void *)&BoardingSchoolHook;
    case HIST_SITE_CALL_TALENT_SCOUT: return (void *)&TalentScoutHook;
    case HIST_SITE_CALL_MARRIAGE: return (void *)&MarriageHook;
    case HIST_SITE_CALL_DIVORCE: return (void *)&DivorceHook;
    case HIST_SITE_CALL_NEW_FAMILY: return (void *)&NewFamilyHook;
    case HIST_SITE_CALL_NEXT_GENERATION: return (void *)&NextGenerationHook;
    case HIST_SITE_CALL_LITTLE_VISITOR1: return (void *)&LittleVisitor1Hook;
    case HIST_SITE_CALL_LITTLE_VISITOR2: return (void *)&LittleVisitor2Hook;
    case HIST_SITE_CALL_ADOPTION: return (void *)&AdoptionHook;
    case HIST_SITE_CALL_RANDOM_EVENT: return (void *)&RandomEventHook;
    case HIST_SITE_CALL_RENAME_MESSAGE: return (void *)&RenameMessageHook;
    case HIST_SITE_CALL_RENAME_SELECTION: return (void *)&RenameSelectionHook;
    case HIST_SITE_CALL_EVICT: return (void *)&EvictHook;
    case HIST_SITE_CALL_START_OVER: return (void *)&StartOverHook;
    }
    return 0;
}

static void SetCallNext(unsigned site, unsigned target) {
    switch (site) {
    case HIST_SITE_CALL_PHYSIOLOGY: NextPhysiology = (ThisVoidFn)target; break;
    case HIST_SITE_CALL_DEATH_TIMEFLOW: NextDeathTimeflow = (TreeVillagerFn)target; break;
    case HIST_SITE_CALL_DEATH_BEHAVIOR: NextDeathBehavior = (TreeVillagerFn)target; break;
    case HIST_SITE_CALL_COLLEGE: NextCollege = (ThisVoidFn)target; break;
    case HIST_SITE_CALL_BOARDING_SCHOOL: NextBoardingSchool = (ThisVoidFn)target; break;
    case HIST_SITE_CALL_TALENT_SCOUT: NextTalentScout = (ThisVoidFn)target; break;
    case HIST_SITE_CALL_MARRIAGE: NextMarriage = (UpdateParentsFn)target; break;
    case HIST_SITE_CALL_DIVORCE: NextDivorce = (ThisVoidFn)target; break;
    case HIST_SITE_CALL_NEW_FAMILY: NextNewFamily = (TreeVillagerBoolFn)target; break;
    case HIST_SITE_CALL_NEXT_GENERATION: NextNextGeneration = (NextGenerationFn)target; break;
    case HIST_SITE_CALL_LITTLE_VISITOR1: NextLittleVisitor1 = (TreeVillagerBoolFn)target; break;
    case HIST_SITE_CALL_LITTLE_VISITOR2: NextLittleVisitor2 = (TreeVillagerBoolFn)target; break;
    case HIST_SITE_CALL_ADOPTION: NextAdoption = (TreeVillagerBoolFn)target; break;
    case HIST_SITE_CALL_RANDOM_EVENT: NextRandomEvent = (DoModalFn)target; break;
    case HIST_SITE_CALL_RENAME_MESSAGE: NextRenameMessage = (ChangeNameFn)target; break;
    case HIST_SITE_CALL_RENAME_SELECTION: NextRenameSelection = (ChangeNameFn)target; break;
    case HIST_SITE_CALL_EVICT: NextEvict = (ThisVoidFn)target; break;
    case HIST_SITE_CALL_START_OVER: NextStartOver = (ThisVoidFn)target; break;
    }
}

static unsigned PinOfSite(unsigned site) {
    for (unsigned e = 0; e < sizeof(HIST_EVIDENCE) / sizeof(HIST_EVIDENCE[0]); ++e)
        if (HIST_EVIDENCE[e].site == site && HIST_EVIDENCE[e].kind == 'L' && HIST_EVIDENCE[e].offset == 0)
            return HIST_EVIDENCE[e].pin;
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
    for (unsigned h = 0; h < sizeof(HIST_CALL_HOOKS) / sizeof(HIST_CALL_HOOKS[0]); ++h) {
        const HistCallHook &hook = HIST_CALL_HOOKS[h];
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
    for (unsigned h = 0; h < sizeof(HIST_ENTRY_HOOKS) / sizeof(HIST_ENTRY_HOOKS[0]); ++h) {
        const HistEntryHook &hook = HIST_ENTRY_HOOKS[h];
        unsigned entry = Sites[hook.site];
        unsigned pin = PinOfSite(hook.site);
        if (pin >= kPinCount || hook.site != HIST_SITE_V_IMPREGNATE || hook.steal < 5 || hook.steal > 16) return false;
        for (unsigned k = 0; k < hook.steal; ++k)
            if (HIST_PINS[pin].mask[k] || ((const unsigned char *)entry)[k] != HIST_PINS[pin].bytes[k]) return false;
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
    unsigned load = 0;
    unsigned vt = SITE(GS_VTABLE);
    if (!SlotChain(vt + HIST_GS_LOAD_VSLOT, SITE(GS_LOAD), &load)) return false;
    NextLoad = (GameStateSlotFn)load;
    HookWrite *wl = AddWrite(plan, vt + HIST_GS_LOAD_VSLOT, 4, true);
    if (!wl) return false;
    *(unsigned *)wl->bytes = (unsigned)&LoadHook;
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
            B200History_Status.writeMask = 0;
            return false;
        }
        B200History_Status.writeMask |= 1u << i;
    }
    return true;
}

static bool SettingOn() {
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    while (Folder[n] && n + 16 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *name = L"vf2history.ini";
    for (unsigned i = 0; name[i]; ++i) path[n++] = name[i];
    path[n] = 0;
    return GetPrivateProfileIntW(L"Patches", L"FamilyHistory", 0, path) == 1;
}

// Called once by the executable's loader, before the game loop starts.
extern "C" __declspec(dllexport) void __cdecl B200History_Startup() {
    static bool started = false;
    if (started) return;
    started = true;
    DWORD n = GetModuleFileNameW(ThisModule, Folder, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    unsigned cut = n;
    while (cut > 0 && Folder[cut - 1] != L'\\') --cut;
    if (!cut) return;
    Folder[cut] = 0;
    Log("vf2history_b200 started");
    bool on = SettingOn();
    B200History_Status.requested = on ? 1u : 0u;
    static Plan plan;
    int built = BuildPlan(on, plan);
    if (built == 0) { Log("Family History is off: the game is stock"); return; }
    if (built < 0) { Log("the executable could not be proved: installing nothing"); return; }
    B200History_Status.resolved = 1;
    ClearSession();
    if (Apply(plan)) {
        B200History_Status.installed = 1;
        Log("Family History installed");
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
#ifdef B200HISTORY_TEST
extern "C" __declspec(dllexport) unsigned __cdecl B200History_TestScanAddress() { return (unsigned)&ScanPattern; }
extern "C" __declspec(dllexport) void __cdecl B200History_TestSetModule(unsigned module) { ThisModule = (HMODULE)module; }
extern "C" __declspec(dllexport) void __cdecl B200History_TestSites(unsigned *out) {
    for (unsigned i = 0; i < HIST_SITE_COUNT; ++i) out[i] = Sites[i];
}
// The whole names read so far are forgotten (the Names files are read again on the next record).
extern "C" __declspec(dllexport) void __cdecl B200History_TestForgetNames() { ForgetWhole(0); }
// The record buffers: [Line, Body, kRecordBytes, the Pending lines buffers (8)] (made now when not yet).
extern "C" __declspec(dllexport) void __cdecl B200History_TestBuffers(unsigned *out) {
    EnsureBuffers();
    out[0] = (unsigned)Line; out[1] = (unsigned)Body; out[2] = kRecordBytes;
    for (unsigned i = 0; i < 8; ++i) out[3 + i] = (unsigned)Waiting[i].lines;
}
// Plans without writing. out: [status, count, then per write: va, len, data, bytes0..3, byte4].
extern "C" __declspec(dllexport) int __cdecl B200History_TestPlan(int enabled, unsigned *out) {
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
        ClearSession();
    }
    return built;
}
#endif
