// vf2revive_b200.dll -- "Revive", the companion DLL for the B200 Virtual Families 2 executable. One feature, one
// DLL: nothing else is installed here. Design: docs/revive.md; the patcher half (the same file format, the backfill
// and the rules) is src/vf2_revive.py.
//
// What it does:
//   * a SNAPSHOT of every family member at the moment they die: the executable's own CVillagerState::SetHealth and
//     AdjustHealth, on the path that stores a cause of death (health 0), call B200Revive_OnDeath(slot) through the
//     generated helper VF2ReviveOnDeath; the snapshot is the villager's record exactly as CVillager::SaveState writes
//     it (the host's saveRecord), with who they are in the current generation of the Family Tree;
//   * the snapshots of a save live beside it, never in it: <save folder>\Virtual Families 2 Patcher Data\Revive\
//     <save file>.dat, the format of src/vf2_revive.py (keyed to the save file's FNV-1a 64 and size like the Up to 28
//     Children file). After theGameState::Save(N) the file of the save the game just moved to N+20 goes with it and
//     a new file is written for N (a temporary file, then a replace); after a Load the file of the loaded save is
//     read. A damaged file is set aside ("<name>.unreadable-K.dat"), never overwritten;
//   * the list the Special Upgrades row "Revive a Family Member" offers (B200Revive_Candidates: the age they come
//     back at is the age they died at when younger than 20, else 20 -- 400 age units -- as when it is not known) and,
//     once the
//     executable has brought one back, its "Arrived" record in the slot's Family History log (B200Revive_Done).
//
// It holds NO game address and patches NO code: everything it needs from the game comes from the host table the
// executable's loader passes to B200Revive_Startup (compiled into every variant from the same source), and the only
// writes into the game's image are the two theGameState vtable slots (Load 13, Save 14), chained exactly as the
// Time Controls and Outfit Pictures DLLs chain them (a slot must hold the stock function or another companion's
// handler). It allocates no executable memory and runs no code from any buffer of its own.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

// ---------------------------------------------------------------- the host table (the executable's side)
struct VF2ReviveHost {
    unsigned magic;                     // 'RVH1'
    unsigned version;                   // 1
    unsigned size;                      // sizeof(VF2ReviveHost)
    int (__cdecl *saveRecord)(int slot, unsigned char *out);    // CVillager::SaveState of household slot, 0x7BC
    const char *(__cdecl *savePath)(int slot);                   // MakeGameStatePath(slot)
    int (__cdecl *currentSlot)();                                 // the family slot loaded (1..5), 0 none
    const unsigned char *(__cdecl *currentFamily)();             // CFamilyTree::GetCurrentFamily (SFamilyRecord)
    int (__cdecl *generations)();                                // CFamilyTree+4
    void **gameStateVtable;                                      // *(void ***)theGameState::Get()
    void *stockLoad;                                             // theGameState::Load (the linker's own symbol)
    void *stockSave;                                             // theGameState::Save
};

static const unsigned kHostMagic = 0x31485652u;   // "RVH1"
static const unsigned kLoadSlot = 13, kSaveSlot = 14;

// ---------------------------------------------------------------- status
struct ReviveStatus {
    unsigned magic, version, requested, installed, entries, captures, lastLoad, lastSave, revived;
};
extern "C" __declspec(dllexport) volatile ReviveStatus B200Revive_Status = { 0x56525632u, 1u, 0, 0, 0, 0, 0, 0, 0 };

static const VF2ReviveHost *Host;
static HMODULE ThisModule;

static void Copy(void *dst, const void *src, unsigned n) {
    volatile unsigned char *d = (volatile unsigned char *)dst;
    const volatile unsigned char *s = (const volatile unsigned char *)src;
    for (unsigned i = 0; i < n; ++i) d[i] = s[i];
}
static void Zero(void *dst, unsigned n) {
    volatile unsigned char *d = (volatile unsigned char *)dst;
    for (unsigned i = 0; i < n; ++i) d[i] = 0;
}
static bool Same(const void *a, const void *b, unsigned n) {
    const unsigned char *x = (const unsigned char *)a, *y = (const unsigned char *)b;
    for (unsigned i = 0; i < n; ++i) if (x[i] != y[i]) return false;
    return true;
}
static unsigned Length(const char *s) { unsigned n = 0; while (s && s[n]) ++n; return n; }
static int I32(const unsigned char *p, unsigned off) { int v; Copy(&v, p + off, 4); return v; }
static unsigned U32(const unsigned char *p, unsigned off) { unsigned v; Copy(&v, p + off, 4); return v; }
static void Put32(unsigned char *p, unsigned off, unsigned v) { Copy(p + off, &v, 4); }
static bool SameName(const unsigned char *a, const unsigned char *b) {   // two NUL-terminated name fields, 25 bytes
    for (unsigned i = 0; i < 25; ++i) {
        if (a[i] != b[i]) return false;
        if (!a[i]) return true;
    }
    return true;
}

// ---------------------------------------------------------------- the file format (src/vf2_revive.py)
static const unsigned kHeader = 52, kEntry = 3504, kMaxEntries = 256, kRecord = 0x7BC;
enum { SRC_CAPTURED = 1, SRC_THIS_SAVE = 2 };
enum { M_UNKNOWN = 0, M_INFERRED = 1, M_EXACT = 2 };
// vf2_revive.FIELDS, in order (the marks bytes at entry +300)
enum { F_NAME, F_FULL_NAME, F_SEX, F_HEAD, F_BODY, F_LIKES, F_DISLIKES, F_LIKES_TEXT, F_DISLIKES_TEXT, F_CAREER,
       F_FERTILITY, F_DESIRE, F_AGE, F_CAUSE, F_PARENTS, F_FIRST_NAME, F_ROLE, F_GENERATION, F_RECORD,
       F_CAREER_LEVEL, F_COUNT };
// entry offsets
enum { E_SOURCE = 0, E_GENERATION = 4, E_ROLE = 8, E_AGE = 12, E_CAUSE = 16, E_SEX = 20, E_HEAD = 24, E_BODY = 28,
       E_CAREER = 32, E_LEVEL = 36, E_FERTILITY = 40, E_DESIRE = 44, E_FIRST = 48, E_BIO0C = 52, E_FHEAD = 56,
       E_FBODY = 60, E_MHEAD = 64, E_MBODY = 68, E_HEIR_SEX = 72, E_HEIR_HEAD = 76, E_HEIR_BODY = 80, E_NAME = 84,
       E_HEIR_NAME = 112, E_FATHER = 140, E_MOTHER = 168, E_LIKES = 196, E_DISLIKES = 208, E_LIKES_TEXT = 220,
       E_DISLIKES_TEXT = 260, E_MARKS = 300, E_RECORD = 320, E_FULL = 2300, E_SPARE = 3500 };
// The entry's last four bytes (vf2_revive SPARE_*): the skin tone and birth tone vf2skin_b200.dll gave at the death
// (B200Skin_ToneOf), the household slot of a revived family member who lives outside the Family Tree, and flags.
enum { S_TONE = E_SPARE, S_BIRTH_TONE = E_SPARE + 1, S_SLOT = E_SPARE + 2, S_FLAGS = E_SPARE + 3 };
enum { FLAG_TONE = 1 };
enum { SRC_MEMBER = 7 };          // revived: lives in the house, outside the Family Tree's records
// the villager record (docs/vf2-save-format.md section 4)
enum { R_AGE = 0x08, R_SEX = 0x0C, R_FIRST = 0x10, R_BIO0C = 0x14, R_NAME = 0x18, R_HEAD = 0x34, R_BODY = 0x38,
       R_FATHER = 0x3C, R_MOTHER = 0x56, R_FHEAD = 0x70, R_FBODY = 0x74, R_MHEAD = 0x78, R_MBODY = 0x7C,
       R_HEALTH = 0xB4, R_CAUSE = 0xB8, R_FERTILITY = 0xF4, R_DESIRE = 0xF8, R_CAREER = 0x140, R_LEVEL = 0x144,
       R_LIKES = 0x150, R_DISLIKES = 0x15C };
// SFamilyRecord / SPeepRecord (section 5)
enum { T_P1 = 0x04, T_P2 = 0xDC, T_COUNT = 0x1B4, T_CHILDREN = 0x1B8, T_PEEP = 0xD8,
       P_PRESENT = 0x1A, P_SEX = 0x1C, P_HEAD = 0x20, P_BODY = 0x24, P_SLOT = 0x28, P_CAREER = 0x30,
       P_LIKES = 0x34, P_DISLIKES = 0x5D };

static unsigned char Entries[kMaxEntries][kEntry];
static unsigned EntryCount;
static unsigned char FileBuffer[kHeader + kMaxEntries * kEntry + 8];
static unsigned char SaveBuffer[0x40000];

static unsigned long long Fnv(const unsigned char *p, unsigned n) {
    unsigned long long h = 0xCBF29CE484222325ull;
    for (unsigned i = 0; i < n; ++i) { h ^= p[i]; h *= 0x100000001B3ull; }
    return h;
}

// the identity key of an entry: generation, the stored name, sex, head, body (vf2_revive.Snapshot.key)
static bool SameKey(const unsigned char *a, const unsigned char *b) {
    return I32(a, E_GENERATION) == I32(b, E_GENERATION) && SameName(a + E_NAME, b + E_NAME) &&
           I32(a, E_SEX) == I32(b, E_SEX) && I32(a, E_HEAD) == I32(b, E_HEAD) && I32(a, E_BODY) == I32(b, E_BODY);
}

// ---------------------------------------------------------------- files
static bool ReadFileAll(const char *path, unsigned char *buf, unsigned cap, unsigned *got) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD size = GetFileSize(h, 0), read = 0;
    bool ok = size != INVALID_FILE_SIZE && size <= cap && ReadFile(h, buf, size, &read, 0) && read == size;
    CloseHandle(h);
    *got = ok ? size : 0;
    return ok;
}

static bool Exists(const char *path) { return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES; }

static void MakeParents(const char *path) {
    char dir[MAX_PATH + 64];
    unsigned n = Length(path);
    if (n >= sizeof(dir)) return;
    Copy(dir, path, n + 1);
    for (unsigned i = 3; i < n; ++i) {
        if (dir[i] != '\\') continue;
        dir[i] = 0;
        CreateDirectoryA(dir, 0);
        dir[i] = '\\';
    }
}

// A temporary file beside it, then a replace, then read back.
static bool WriteReplace(const char *path, const unsigned char *data, unsigned len) {
    char tmp[MAX_PATH + 80];
    unsigned n = Length(path);
    if (n + 16 >= sizeof(tmp)) return false;
    Copy(tmp, path, n);
    Copy(tmp + n, ".revive-tmp", 12);
    MakeParents(path);
    HANDLE h = CreateFileA(tmp, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    BOOL ok = WriteFile(h, data, len, &written, 0) && written == len && FlushFileBuffers(h);
    CloseHandle(h);
    if (!ok || !MoveFileExA(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(tmp);
        return false;
    }
    unsigned got = 0;
    static unsigned char back[sizeof(FileBuffer)];
    return ReadFileAll(path, back, sizeof(back), &got) && got == len && Same(back, data, len);
}

// "<save folder>\Virtual Families 2 Patcher Data\Revive\<save file>.dat" and the save file's own path.
static bool Paths(int number, char *save, char *sidecar, unsigned cap) {
    const char *p = Host->savePath(number);
    unsigned n = Length(p);
    if (!p || !n || n + 64 >= cap) return false;
    Copy(save, p, n + 1);
    unsigned cut = n;
    while (cut && p[cut - 1] != '\\' && p[cut - 1] != '/') --cut;
    static const char mid[] = "Virtual Families 2 Patcher Data\\Revive\\";
    unsigned m = Length(mid);
    if (cut + m + (n - cut) + 5 >= cap) return false;
    Copy(sidecar, p, cut);
    Copy(sidecar + cut, mid, m);
    Copy(sidecar + cut + m, p + cut, n - cut);
    Copy(sidecar + cut + m + (n - cut), ".dat", 5);
    return true;
}

// 1 a valid file (entries in out), 0 none, -1 damaged
static int ReadSidecar(const char *path, unsigned char (*out)[kEntry], unsigned *count,
                       unsigned long long *hash, unsigned *size) {
    unsigned got = 0;
    *count = 0;
    if (!Exists(path)) return 0;
    if (!ReadFileAll(path, FileBuffer, sizeof(FileBuffer), &got)) return -1;
    if (got < kHeader + 8 || !Same(FileBuffer, "VF2REVIV", 8) || !Same(FileBuffer + 12, "VF2B200\0", 8)) return -1;
    unsigned n = U32(FileBuffer, 48);
    if (U32(FileBuffer, 8) != 1 || U32(FileBuffer, 20) != got || n > kMaxEntries || got != kHeader + n * kEntry + 8)
        return -1;
    unsigned long long sum;
    Copy(&sum, FileBuffer + got - 8, 8);
    if (sum != Fnv(FileBuffer, got - 8)) return -1;
    Copy(hash, FileBuffer + 24, 8);
    *size = U32(FileBuffer, 32);
    for (unsigned i = 0; i < n; ++i) {
        const unsigned char *e = FileBuffer + kHeader + i * kEntry;
        for (unsigned f = 0; f < F_COUNT; ++f) if (e[E_MARKS + f] > M_EXACT) return -1;
        if (U32(e, E_SOURCE) < 1 || U32(e, E_SOURCE) > SRC_MEMBER) return -1;
        Copy(out[i], e, kEntry);
    }
    *count = n;
    return 1;
}

static void SetAside(const char *path) {
    char aside[MAX_PATH + 80];
    unsigned n = Length(path);
    if (n < 4 || n + 24 >= sizeof(aside)) return;
    for (unsigned k = 1; k < 1000; ++k) {
        Copy(aside, path, n - 4);
        unsigned m = n - 4;
        static const char mid[] = ".unreadable-";
        Copy(aside + m, mid, 12);
        m += 12;
        char digits[8];
        unsigned d = 0, v = k;
        do { digits[d++] = (char)('0' + v % 10); v /= 10; } while (v);
        while (d) aside[m++] = digits[--d];
        Copy(aside + m, ".dat", 5);
        if (!Exists(aside)) { MoveFileExA(path, aside, 0); return; }
    }
}

static int MakeFile(const unsigned char *save, unsigned saveLen) {     // into FileBuffer, sorted as make_file
    unsigned total = kHeader + EntryCount * kEntry + 8;
    Zero(FileBuffer, kHeader);
    Copy(FileBuffer, "VF2REVIV", 8);
    Put32(FileBuffer, 8, 1);
    Copy(FileBuffer + 12, "VF2B200\0", 8);
    Put32(FileBuffer, 20, total);
    unsigned long long h = Fnv(save, saveLen);
    Copy(FileBuffer + 24, &h, 8);
    Put32(FileBuffer, 32, saveLen);
    Put32(FileBuffer, 48, EntryCount);
    for (unsigned i = 0; i < EntryCount; ++i) Copy(FileBuffer + kHeader + i * kEntry, Entries[i], kEntry);
    unsigned long long sum = Fnv(FileBuffer, total - 8);
    Copy(FileBuffer + total - 8, &sum, 8);
    return (int)total;
}

// ---------------------------------------------------------------- the current generation
static const unsigned char *Peep(const unsigned char *rec, int place) {
    return place == 0 ? rec + T_P1 : place == 1 ? rec + T_P2 : rec + T_CHILDREN + (unsigned)(place - 2) * T_PEEP;
}

// Where a villager record stands in the current record: 0 parent 1, 1 parent 2, 2 + k child k, -1 not there.
static int RoleOf(const unsigned char *rec, const unsigned char *r, int slot) {
    if (!rec) return -1;
    int count = I32(rec, T_COUNT);
    if (count < 0) count = 0;
    if (count > 6) count = 6;
    for (int place = 0; place < 2 + count; ++place) {
        const unsigned char *p = Peep(rec, place);
        if (!p[P_PRESENT]) continue;
        if (SameName(p, r + R_NAME) && I32(p, P_SEX) == I32(r, R_SEX) && I32(p, P_HEAD) == I32(r, R_HEAD) &&
            (I32(p, P_SLOT) == slot || I32(p, P_SLOT) == -1))
            return place;
    }
    return -1;
}

// The snapshot of the record just taken (exact: it is the record as they died).
static void Capture(const unsigned char *r, int slot, unsigned source) {
    const unsigned char *rec = Host->currentFamily ? Host->currentFamily() : 0;
    int gen = Host->generations ? Host->generations() : 0;
    if (!rec || gen <= 0) return;
    static unsigned char e[kEntry];
    Zero(e, kEntry);
    Put32(e, E_SOURCE, source);
    Put32(e, E_GENERATION, (unsigned)gen);
    int role = RoleOf(rec, r, slot);
    Put32(e, E_ROLE, (unsigned)role);
    Put32(e, E_AGE, U32(r, R_AGE));
    Put32(e, E_CAUSE, U32(r, R_CAUSE));
    Put32(e, E_SEX, U32(r, R_SEX));
    Put32(e, E_HEAD, U32(r, R_HEAD));
    Put32(e, E_BODY, U32(r, R_BODY));
    Put32(e, E_CAREER, U32(r, R_CAREER));
    Put32(e, E_LEVEL, U32(r, R_LEVEL));
    Put32(e, E_FERTILITY, U32(r, R_FERTILITY));
    Put32(e, E_DESIRE, U32(r, R_DESIRE));
    Put32(e, E_FIRST, U32(r, R_FIRST));
    Put32(e, E_BIO0C, U32(r, R_BIO0C));
    Put32(e, E_FHEAD, U32(r, R_FHEAD));
    Put32(e, E_FBODY, U32(r, R_FBODY));
    Put32(e, E_MHEAD, U32(r, R_MHEAD));
    Put32(e, E_MBODY, U32(r, R_MBODY));
    const unsigned char *heir = rec + T_P1;
    Put32(e, E_HEIR_SEX, U32(heir, P_SEX));
    Put32(e, E_HEIR_HEAD, U32(heir, P_HEAD));
    Put32(e, E_HEIR_BODY, U32(heir, P_BODY));
    for (unsigned i = 0; i < 25 && r[R_NAME + i]; ++i) e[E_NAME + i] = r[R_NAME + i];
    for (unsigned i = 0; i < 25 && heir[i]; ++i) e[E_HEIR_NAME + i] = heir[i];
    for (unsigned i = 0; i < 25 && r[R_FATHER + i]; ++i) e[E_FATHER + i] = r[R_FATHER + i];
    for (unsigned i = 0; i < 25 && r[R_MOTHER + i]; ++i) e[E_MOTHER + i] = r[R_MOTHER + i];
    Copy(e + E_LIKES, r + R_LIKES, 12);
    Copy(e + E_DISLIKES, r + R_DISLIKES, 12);
    if (role >= 0) {
        const unsigned char *p = Peep(rec, role);
        for (unsigned i = 0; i < 39 && p[P_LIKES + i]; ++i) e[E_LIKES_TEXT + i] = p[P_LIKES + i];
        for (unsigned i = 0; i < 39 && p[P_DISLIKES + i]; ++i) e[E_DISLIKES_TEXT + i] = p[P_DISLIKES + i];
        e[E_MARKS + F_LIKES_TEXT] = e[E_MARKS + F_DISLIKES_TEXT] = M_EXACT;
        e[E_MARKS + F_ROLE] = M_EXACT;
    }
    Copy(e + E_RECORD, r, kRecord);
    // Skin Tones (vf2skin_b200.dll, when it is loaded): the tone and the birth tone, given back at a revival
    HMODULE skin = GetModuleHandleW(L"vf2skin_b200.dll");
    typedef int (__cdecl *ToneOfFn)(int slot);
    ToneOfFn toneOf = skin ? (ToneOfFn)GetProcAddress(skin, "B200Skin_ToneOf") : 0;
    int tone = toneOf ? toneOf(slot) : -1;
    if (tone >= 0) {
        e[S_TONE] = (unsigned char)(tone & 0xFF);
        e[S_BIRTH_TONE] = (unsigned char)((tone >> 8) & 0xFF);
        e[S_FLAGS] |= FLAG_TONE;
    }
    static const unsigned char exact[] = { F_NAME, F_SEX, F_HEAD, F_BODY, F_LIKES, F_DISLIKES, F_CAREER, F_FERTILITY,
                                           F_DESIRE, F_AGE, F_CAUSE, F_PARENTS, F_FIRST_NAME, F_GENERATION, F_RECORD,
                                           F_CAREER_LEVEL };
    for (unsigned i = 0; i < sizeof(exact); ++i) e[E_MARKS + exact[i]] = M_EXACT;
    // the whole name is the Names file's: B200Revive leaves it to the reader (vf2_revive and the log) when the
    // stored name is a short form; the stored name is the whole name otherwise
    e[E_MARKS + F_FULL_NAME] = M_EXACT;
    for (unsigned i = 0; i < EntryCount; ++i) {
        if (!SameKey(Entries[i], e)) continue;
        if (U32(Entries[i], E_SOURCE) == SRC_CAPTURED) return;      // the first capture is the death itself
        Copy(Entries[i], e, kEntry);                                 // a capture always wins
        ++B200Revive_Status.captures;
        return;
    }
    if (EntryCount >= kMaxEntries) return;
    Copy(Entries[EntryCount++], e, kEntry);
    B200Revive_Status.entries = EntryCount;
    ++B200Revive_Status.captures;
}

static unsigned char RecordBuffer[kRecord];

// Every family member of the current generation lying dead in the house (a death before the patch, a corpse
// loaded from the save): their record as the save holds it.
static void CaptureTheDead(unsigned source) {
    const unsigned char *rec = Host->currentFamily ? Host->currentFamily() : 0;
    if (!rec) return;
    for (int slot = 0; slot < 30; ++slot) {
        if (!Host->saveRecord(slot, RecordBuffer)) continue;
        if (I32(RecordBuffer, R_HEALTH) > 0 || !RecordBuffer[R_NAME]) continue;     // dead, and someone
        if (RoleOf(rec, RecordBuffer, slot) < 0) continue;                         // of the current generation
        Capture(RecordBuffer, slot, source);
    }
}

// ---------------------------------------------------------------- the game's Load and Save (vtable 13 / 14)
typedef bool (__fastcall *GameStateSlotFn)(void *state, void *, int slot);
static GameStateSlotFn NextLoad, NextSave;
static int LoadedSlot;

static bool __fastcall LoadHook(void *state, void *edx, int slot) {
    bool ok = NextLoad(state, edx, slot);
    if (!ok || slot < 1 || slot > 5) return ok;
    EntryCount = 0;
    LoadedSlot = slot;
    char save[MAX_PATH + 64], side[MAX_PATH + 128];
    if (!Paths(slot, save, side, sizeof(side))) return ok;
    unsigned long long hash = 0;
    unsigned size = 0, n = 0;
    int r = ReadSidecar(side, Entries, &n, &hash, &size);
    if (r < 0) { SetAside(side); B200Revive_Status.lastLoad = 3; }
    else { EntryCount = n; B200Revive_Status.lastLoad = r ? 1 : 2; }
    CaptureTheDead(SRC_THIS_SAVE);
    B200Revive_Status.entries = EntryCount;
    return ok;
}

static bool __fastcall SaveHook(void *state, void *edx, int slot) {
    bool ok = NextSave(state, edx, slot);
    if (!ok || slot < 1 || slot > 5 || slot != LoadedSlot) return ok;
    char save[MAX_PATH + 64], side[MAX_PATH + 128], prevSave[MAX_PATH + 64], prevSide[MAX_PATH + 128];
    if (!Paths(slot, save, side, sizeof(side)) || !Paths(slot + 20, prevSave, prevSide, sizeof(prevSide)))
        return ok;
    // the game moved N to N+20: the file that described it goes with it
    unsigned got = 0;
    static unsigned char scratch[kMaxEntries][kEntry];
    unsigned long long hash = 0;
    unsigned size = 0, n = 0;
    int r = ReadSidecar(side, scratch, &n, &hash, &size);
    if (r > 0 && ReadFileAll(prevSave, SaveBuffer, sizeof(SaveBuffer), &got) && got == size &&
        Fnv(SaveBuffer, got) == hash) {
        unsigned prevN = 0;
        unsigned long long ph = 0;
        unsigned ps = 0;
        if (ReadSidecar(prevSide, scratch, &prevN, &ph, &ps) < 0) SetAside(prevSide);
        MoveFileExA(side, prevSide, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
    } else if (r < 0) {
        SetAside(side);
    }
    CaptureTheDead(SRC_THIS_SAVE);
    if (!EntryCount) { B200Revive_Status.lastSave = 2; return ok; }
    if (!ReadFileAll(save, SaveBuffer, sizeof(SaveBuffer), &got) || !got) { B200Revive_Status.lastSave = 3; return ok; }
    int len = MakeFile(SaveBuffer, got);
    B200Revive_Status.lastSave = WriteReplace(side, FileBuffer, (unsigned)len) ? 1 : 3;
    return ok;
}

// ---------------------------------------------------------------- exports for the executable
extern "C" __declspec(dllexport) void __cdecl B200Revive_OnDeath(int slot) {
    if (!B200Revive_Status.installed || slot < 0 || slot >= 30) return;
    if (!Host->saveRecord(slot, RecordBuffer) || I32(RecordBuffer, R_HEALTH) > 0) return;
    Capture(RecordBuffer, slot, SRC_CAPTURED);
}

// What the executable needs to bring one back (B200Revive_Candidates fills these).
struct B200ReviveCandidate {
    int index;                  // the snapshot's index (for B200Revive_Done)
    int role;                   // 0 parent 1, 1 parent 2, 2.. a child, -1 not in the tree
    int ageUnits;               // the age they return at: their age at death below 20 (400 units), else 20
    int sex, head, body;
    char name[28];              // the name as the save stores it
    const unsigned char *entry; // the whole snapshot (vf2_revive's entry layout)
};

static bool AliveNow(const unsigned char *e) {
    for (int slot = 0; slot < 30; ++slot) {
        if (!Host->saveRecord(slot, RecordBuffer)) continue;
        if (!RecordBuffer[0] || I32(RecordBuffer, R_HEALTH) <= 0) continue;
        if (SameName(RecordBuffer + R_NAME, e + E_NAME) && I32(RecordBuffer, R_SEX) == I32(e, E_SEX) &&
            I32(RecordBuffer, R_HEAD) == I32(e, E_HEAD) && I32(RecordBuffer, R_BODY) == I32(e, E_BODY))
            return true;
    }
    return false;
}

// Younger than 20 at death: that age; 20 or older, or not known: 20 (the owner's rule).
static const int kAdultReturnUnits = 400;
static int ReviveAge(const unsigned char *e) {
    if (e[E_MARKS + F_AGE] == M_UNKNOWN || I32(e, E_AGE) < 0) return kAdultReturnUnits;
    int age = I32(e, E_AGE);
    return age >= kAdultReturnUnits ? kAdultReturnUnits : age;
}

extern "C" __declspec(dllexport) int __cdecl B200Revive_Candidates(B200ReviveCandidate *out, int max) {
    if (!B200Revive_Status.installed || !out || max <= 0) return 0;
    const unsigned char *rec = Host->currentFamily();
    int gen = Host->generations();
    if (!rec || gen <= 0) return 0;
    const unsigned char *heir = rec + T_P1;
    int n = 0;
    for (unsigned i = 0; i < EntryCount && n < max; ++i) {
        const unsigned char *e = Entries[i];
        if (I32(e, E_GENERATION) != gen || !SameName(e + E_HEIR_NAME, heir) || I32(e, E_HEIR_SEX) != I32(heir, P_SEX) ||
            I32(e, E_HEIR_HEAD) != I32(heir, P_HEAD) || I32(e, E_HEIR_BODY) != I32(heir, P_BODY))
            continue;                                       // the current generation of this family only
        if (e[E_MARKS + F_SEX] != M_EXACT || e[E_MARKS + F_HEAD] != M_EXACT || e[E_MARKS + F_BODY] != M_EXACT ||
            e[E_MARKS + F_NAME] != M_EXACT)
            continue;                                       // who they were must be known exactly
        if (U32(e, E_SOURCE) == SRC_MEMBER) continue;      // revived already: lives in the house
        if (AliveNow(e)) continue;                          // only the dead
        int age = ReviveAge(e);
        B200ReviveCandidate &c = out[n++];
        Zero(&c, sizeof(c));
        c.index = (int)i;
        c.role = I32(e, E_ROLE);
        c.ageUnits = age;
        c.sex = I32(e, E_SEX);
        c.head = I32(e, E_HEAD);
        c.body = I32(e, E_BODY);
        for (unsigned k = 0; k < 25 && e[E_NAME + k]; ++k) c.name[k] = (char)e[E_NAME + k];
        c.entry = e;
    }
    return n;
}

// ---- the "Arrived" record in the slot's Family History log, when the slot has one (the Family History DLL's
// layout; its own record numbers are read from the files at every write, so a record appended here is counted)
static char LogBuffer[0x100000];
static char Line[8192];                         // a record: a whole name is up to 3,600 bytes

static unsigned AppendText(char *out, unsigned n, const char *s) { while (*s && n + 1 < sizeof(Line)) out[n++] = *s++; out[n] = 0; return n; }
static unsigned AppendNum(char *out, unsigned n, int v) {
    char d[12];
    unsigned k = 0;
    unsigned u = v < 0 ? (unsigned)-v : (unsigned)v;
    if (v < 0 && n + 1 < sizeof(Line)) out[n++] = '-';
    do { d[k++] = (char)('0' + u % 10); u /= 10; } while (u && k < 11);
    while (k && n + 1 < sizeof(Line)) out[n++] = d[--k];
    out[n] = 0;
    return n;
}

static bool LogFolder(int slot, char *out, unsigned cap) {
    const char *p = Host->savePath(slot);
    unsigned n = Length(p), cut = n;
    while (cut && p[cut - 1] != '\\' && p[cut - 1] != '/') --cut;
    static const char mid[] = "Virtual Families 2 Patcher\\Save ";
    if (!n || cut + 80 >= cap) return false;
    Copy(out, p, cut);
    unsigned m = cut;
    m = AppendText(out, m, mid);
    m = AppendNum(out, m, slot);
    AppendText(out, m, "\\Logs\\Family History\\Family History ");
    return true;
}

static unsigned Highest(const char *text, unsigned len, const char *kind) {
    unsigned best = 0, m = Length(kind);
    for (unsigned i = 0; i < len; ++i) {
        if ((i && text[i - 1] != '\n') || text[i] != '[') continue;
        unsigned j = i;
        while (j < len && text[j] != ']' && text[j] != '\n') ++j;
        j += 2;
        if (j + m + 1 > len || !Same(text + j, kind, m) || text[j + m] != ' ') continue;
        unsigned v = 0;
        for (j += m + 1; j < len && text[j] >= '0' && text[j] <= '9' && v < 100000000u; ++j) v = v * 10 + (text[j] - '0');
        if (v > best) best = v;
    }
    return best;
}

// The Family History DLL (vf2history_b200.dll), when it is loaded: the whole name for a stored one, and a revival's
// slot, whose earlier death it forgets so the person's next death is logged when it happens.
typedef int (__cdecl *HistoryLogNameFn)(const char *stored, char *out, int cap);
typedef void (__cdecl *HistoryRevivedFn)(int slot);
static FARPROC History(const char *name) {
    HMODULE h = GetModuleHandleW(L"vf2history_b200.dll");
    return h ? GetProcAddress(h, name) : 0;
}

static char Shown[4096];

// The name a record writes: the whole name (the Family History DLL reads it from the slot's Names file, as for its own
// records), else the snapshot's whole name (a backfilled one keeps it), else the name the save stores.
static const char *LogName(const unsigned char *e, const char *stored) {
    HistoryLogNameFn whole = (HistoryLogNameFn)History("B200History_LogName");
    if (whole && whole(stored, Shown, (int)sizeof(Shown)) > 0) return Shown;
    if (e[E_FULL]) {
        unsigned n = 0;
        while (n < 1199 && n + 1 < sizeof(Shown) && e[E_FULL + n]) { Shown[n] = (char)e[E_FULL + n]; ++n; }
        Shown[n] = 0;
        return Shown;
    }
    return stored;
}

static void LogRevived(int slot, const unsigned char *e, int ageUnits, const char *how) {
    char base[MAX_PATH + 128], path[MAX_PATH + 160];
    if (!LogFolder(slot, base, sizeof(base))) return;
    unsigned arrived = 0, newest = 0;
    for (unsigned k = 1; k < 1000; ++k) {
        unsigned n = AppendText(path, 0, base);
        n = AppendNum(path, n, (int)k);
        AppendText(path, n, ".txt");
        if (!Exists(path)) break;
        newest = k;
        unsigned got = 0;
        if (ReadFileAll(path, (unsigned char *)LogBuffer, sizeof(LogBuffer), &got)) {
            unsigned h = Highest(LogBuffer, got, "Arrived");
            if (h > arrived) arrived = h;
        }
    }
    if (!newest) return;                         // no Family History log for this slot: nothing is started here
    unsigned n = AppendText(path, 0, base);
    n = AppendNum(path, n, (int)newest);
    AppendText(path, n, ".txt");
    SYSTEMTIME now;
    GetLocalTime(&now);
    unsigned k = 0;
    k = AppendText(Line, k, "[");
    k = AppendNum(Line, k, now.wYear); k = AppendText(Line, k, "-");
    if (now.wMonth < 10) k = AppendText(Line, k, "0");
    k = AppendNum(Line, k, now.wMonth); k = AppendText(Line, k, "-");
    if (now.wDay < 10) k = AppendText(Line, k, "0");
    k = AppendNum(Line, k, now.wDay); k = AppendText(Line, k, " ");
    if (now.wHour < 10) k = AppendText(Line, k, "0");
    k = AppendNum(Line, k, now.wHour); k = AppendText(Line, k, ":");
    if (now.wMinute < 10) k = AppendText(Line, k, "0");
    k = AppendNum(Line, k, now.wMinute); k = AppendText(Line, k, ":");
    if (now.wSecond < 10) k = AppendText(Line, k, "0");
    k = AppendNum(Line, k, now.wSecond);
    k = AppendText(Line, k, "] Arrived ");
    k = AppendNum(Line, k, (int)arrived + 1);
    k = AppendText(Line, k, "\r\n  Name: ");
    char name[28];
    Zero(name, sizeof(name));
    for (unsigned i = 0; i < 25 && e[E_NAME + i]; ++i) name[i] = (char)e[E_NAME + i];
    k = AppendText(Line, k, LogName(e, name));
    k = AppendText(Line, k, "\r\n  Age at arrival: ");
    k = AppendNum(Line, k, ageUnits / 20);
    k = AppendText(Line, k, "\r\n  Sex: ");
    k = AppendText(Line, k, I32(e, E_SEX) == 1 ? "Female" : "Male");
    k = AppendText(Line, k, "\r\n  Head: ");
    k = AppendNum(Line, k, I32(e, E_HEAD));
    k = AppendText(Line, k, "\r\n  Body: ");
    k = AppendNum(Line, k, I32(e, E_BODY));
    k = AppendText(Line, k, "\r\n  How: Revived (Revive a Family Member)\r\n  Family role: ");
    k = AppendText(Line, k, how);
    k = AppendText(Line, k, "\r\n  Generation: ");
    k = AppendNum(Line, k, I32(e, E_GENERATION));
    k = AppendText(Line, k, "\r\n\r\n");
    HANDLE h = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(h, Line, k, &written, 0);
    CloseHandle(h);
}

// The executable brought snapshot `index` back into household slot `newSlot` as `role` ("Parent", "Parent
// (married in)", "Child", or "Family member": a remarried partner's late spouse, outside the Family Tree's records).
// Their skin tone goes back to them (Skin Tones). A tree member leaves the list (they live again; a later death is
// captured anew); a family member stays in it as a member (SRC_MEMBER, their slot) so the executable can draw them on
// the game's Family Tree screen under the current spouse. Logged.
extern "C" __declspec(dllexport) void __cdecl B200Revive_Done(int index, int newSlot, int ageUnits, const char *role) {
    if (!B200Revive_Status.installed || index < 0 || (unsigned)index >= EntryCount) return;
    unsigned char *e = Entries[index];
    if (e[S_FLAGS] & FLAG_TONE) {
        HMODULE skin = GetModuleHandleW(L"vf2skin_b200.dll");
        typedef void (__cdecl *ToneGiveFn)(int slot, int tone, int birthTone);
        ToneGiveFn give = skin ? (ToneGiveFn)GetProcAddress(skin, "B200Skin_ToneGive") : 0;
        if (give) give(newSlot, e[S_TONE], e[S_BIRTH_TONE]);
    }
    HistoryRevivedFn revived = (HistoryRevivedFn)History("B200History_Revived");
    if (revived && newSlot >= 0 && newSlot < 30) revived(newSlot);
    bool member = role && Same(role, "Family member", 14);
    int slot = Host->currentSlot();
    if (slot >= 1 && slot <= 5)
        LogRevived(slot, e, ageUnits, member ? "Family member (shown under the current spouse in the Family Tree)"
                                             : role ? role : "Child");
    if (member && newSlot >= 0 && newSlot < 30) {
        Put32(e, E_SOURCE, SRC_MEMBER);
        e[S_SLOT] = (unsigned char)newSlot;
    } else {
        for (unsigned i = (unsigned)index; i + 1 < EntryCount; ++i) Copy(Entries[i], Entries[i + 1], kEntry);
        --EntryCount;
    }
    B200Revive_Status.entries = EntryCount;
    ++B200Revive_Status.revived;
}

// The revived family members who live outside the Family Tree's records, as the house holds them now (their slot
// still them, alive and at home), of the current generation of this family: the executable draws them under the
// current spouse on the game's Family Tree screen.
struct B200ReviveMember {
    int slot, sex, head, body;
    char name[28];
    const unsigned char *entry;
};

extern "C" __declspec(dllexport) int __cdecl B200Revive_Members(B200ReviveMember *out, int max) {
    if (!B200Revive_Status.installed || !out || max <= 0) return 0;
    const unsigned char *rec = Host->currentFamily();
    int gen = Host->generations();
    if (!rec || gen <= 0) return 0;
    int n = 0;
    for (unsigned i = 0; i < EntryCount && n < max; ++i) {
        const unsigned char *e = Entries[i];
        if (U32(e, E_SOURCE) != SRC_MEMBER || I32(e, E_GENERATION) != gen) continue;
        int slot = e[S_SLOT];
        if (slot >= 30 || !Host->saveRecord(slot, RecordBuffer)) continue;
        if (!RecordBuffer[0] || RecordBuffer[1] || I32(RecordBuffer, R_HEALTH) <= 0) continue;
        if (!SameName(RecordBuffer + R_NAME, e + E_NAME) || I32(RecordBuffer, R_SEX) != I32(e, E_SEX) ||
            I32(RecordBuffer, R_HEAD) != I32(e, E_HEAD) || I32(RecordBuffer, R_BODY) != I32(e, E_BODY))
            continue;
        B200ReviveMember &m = out[n++];
        Zero(&m, sizeof(m));
        m.slot = slot;
        m.sex = I32(e, E_SEX);
        m.head = I32(e, E_HEAD);
        m.body = I32(e, E_BODY);
        for (unsigned k = 0; k < 25 && e[E_NAME + k]; ++k) m.name[k] = (char)e[E_NAME + k];
        m.entry = e;
    }
    return n;
}

// ---------------------------------------------------------------- install
static wchar_t Folder[MAX_PATH];

static bool SettingOn() {
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    while (Folder[n] && n + 16 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *name = L"vf2revive.ini";
    for (unsigned i = 0; name[i]; ++i) path[n++] = name[i];
    path[n] = 0;
    return GetPrivateProfileIntW(L"Patches", L"Revive", 0, path) == 1;
}

static bool InImage(unsigned va) {
    HMODULE exe = GetModuleHandleW(0);
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)exe;
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)((const unsigned char *)exe + dos->e_lfanew);
    return va >= (unsigned)exe && va < (unsigned)exe + nt->OptionalHeader.SizeOfImage;
}

// A vtable slot holds the stock function, or a handler outside the executable (another companion DLL's).
static bool SlotChain(void **slot, void *stock, void **now) {
    *now = *slot;
    return *now == stock || (*now && !InImage((unsigned)*now));
}

// The two vtable writes (data, never code): PAGE_READWRITE for the write, the old protection put back.
static bool WriteSlot(void **slot, void *value) {
    DWORD old = 0, ignored = 0;
    if (!VirtualProtect(slot, 4, PAGE_READWRITE, &old)) return false;
    *(void *volatile *)slot = value;
    return VirtualProtect(slot, 4, old, &ignored) != FALSE;
}

// vf2revive.log beside the DLL: one line per start, as the other companion DLLs write theirs.
static void StartLog(const char *line) {
    wchar_t path[MAX_PATH];
    unsigned n = 0;
    while (Folder[n] && n + 16 < MAX_PATH) { path[n] = Folder[n]; ++n; }
    const wchar_t *name = L"vf2revive.log";
    for (unsigned i = 0; name[i]; ++i) path[n++] = name[i];
    path[n] = 0;
    HANDLE h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(h, line, Length(line), &written, 0);
    WriteFile(h, "\r\n", 2, &written, 0);
    CloseHandle(h);
}

extern "C" __declspec(dllexport) void __cdecl B200Revive_Startup(const VF2ReviveHost *host) {
    if (B200Revive_Status.installed) return;
    GetModuleFileNameW(ThisModule, Folder, MAX_PATH);
    unsigned cut = 0;
    for (unsigned i = 0; Folder[i]; ++i) if (Folder[i] == L'\\') cut = i + 1;
    Folder[cut] = 0;
    if (!SettingOn()) { StartLog("Revive not installed: vf2revive.ini does not say Revive=1"); return; }
    B200Revive_Status.requested = 1;
    if (!host || host->magic != kHostMagic || host->version != 1 || host->size != sizeof(VF2ReviveHost) ||
        !host->saveRecord || !host->savePath || !host->currentSlot || !host->currentFamily || !host->generations ||
        !host->gameStateVtable || !host->stockLoad || !host->stockSave) {
        StartLog("Revive not installed: the executable's host table is not one this DLL knows");
        return;
    }
    void *load = 0, *save = 0;
    void **vt = host->gameStateVtable;
    if (!SlotChain(vt + kLoadSlot, host->stockLoad, &load) || !SlotChain(vt + kSaveSlot, host->stockSave, &save)) {
        StartLog("Revive not installed: theGameState's Load / Save slots hold something unknown");
        return;
    }
    Host = host;
    NextLoad = (GameStateSlotFn)load;
    NextSave = (GameStateSlotFn)save;
    if (!WriteSlot(vt + kLoadSlot, (void *)&LoadHook)) { StartLog("Revive not installed: the Load slot write failed"); return; }
    if (!WriteSlot(vt + kSaveSlot, (void *)&SaveHook)) {
        WriteSlot(vt + kLoadSlot, load);
        StartLog("Revive not installed: the Save slot write failed");
        return;
    }
    B200Revive_Status.installed = 1;
    StartLog("Revive installed");
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) ThisModule = instance;
    return TRUE;
}
