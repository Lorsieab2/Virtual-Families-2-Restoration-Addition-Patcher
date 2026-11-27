// The test harness of vf2revive_b200.dll (tests/test_b200_revive.py): a stand-in for the executable's host table.
// It keeps 30 villager records laid out as CVillager::SaveState writes them and one Family Tree record laid out as
// SFamilyRecord (docs/vf2-save-format.md sections 4 and 5), a theGameState vtable whose slots 13 / 14 are its own Load
// and Save (Save moves file N to N+20 and writes N, as ldwGameState::Save does), loads the DLL from its own folder and
// runs the commands on its command line, printing what the DLL answers. Never shipped.
//
//   vf2revive_harness.exe <save folder> <command> ...
//     family                 Ann (heir, slot 0), Bob (spouse, slot 1), Cal and Fay (children, slots 2 and 3)
//     age <slot> <units>     kill <slot> <cause>     load <n>     save <n>     cands     done <i> <slot> <role>
//     status                 vtable                  hostbad
//     (first) skin / history: load the Skin Tones / Family History stand-in      forgot
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct VF2ReviveHost {
    unsigned magic, version, size;
    int (__cdecl *saveRecord)(int slot, unsigned char *out);
    const char *(__cdecl *savePath)(int slot);
    int (__cdecl *currentSlot)();
    const unsigned char *(__cdecl *currentFamily)();
    int (__cdecl *generations)();
    void **gameStateVtable;
    void *stockLoad;
    void *stockSave;
};
struct Candidate { int index, role, ageUnits, sex, head, body; char name[28]; const unsigned char *entry; };
struct Member { int slot, sex, head, body; char name[28]; const unsigned char *entry; };
struct Status { unsigned magic, version, requested, installed, entries, captures, lastLoad, lastSave, revived; };

static unsigned char Records[30][0x7BC];
static unsigned char Family[0x6C8];
static char Folder[MAX_PATH];
static char PathBuf[MAX_PATH + 64];
static int Slot = 1;

static int __cdecl SaveRecord(int slot, unsigned char *out) {
    if (slot < 0 || slot >= 30) return 0;
    memcpy(out, Records[slot], 0x7BC);
    return 1;
}
static const char *__cdecl SavePath(int slot) {
    sprintf_s(PathBuf, "%s\\Virtual Families 2%d.ldw", Folder, slot);
    return PathBuf;
}
static int __cdecl CurrentSlot() { return Slot; }
static const unsigned char *__cdecl CurrentFamily() { return Family[0] ? Family : 0; }
static int __cdecl Generations() { return Family[0] ? 1 : 0; }

static bool __fastcall StockLoad(void *, void *, int slot) {
    char path[MAX_PATH + 64];
    sprintf_s(path, "%s\\Virtual Families 2%d.ldw", Folder, slot);
    FILE *f = 0;
    if (fopen_s(&f, path, "rb") || !f) return false;
    size_t got = fread(Records, 1, sizeof(Records), f);
    got += fread(Family, 1, sizeof(Family), f);
    fclose(f);
    Slot = slot;
    return got == sizeof(Records) + sizeof(Family);
}
static bool __fastcall StockSave(void *, void *, int slot) {
    char path[MAX_PATH + 64], prev[MAX_PATH + 64];
    sprintf_s(path, "%s\\Virtual Families 2%d.ldw", Folder, slot);
    sprintf_s(prev, "%s\\Virtual Families 2%d.ldw", Folder, slot + 20);
    DeleteFileA(prev);
    MoveFileA(path, prev);
    FILE *f = 0;
    if (fopen_s(&f, path, "wb") || !f) return false;
    fwrite(Records, 1, sizeof(Records), f);
    fwrite(Family, 1, sizeof(Family), f);
    fclose(f);
    return true;
}
typedef bool (__fastcall *SlotFn)(void *, void *, int);
static void *Vtable[20];
static void *GameState[1] = { Vtable };

static void Villager(int slot, const char *name, int sex, int head, int body, int age) {
    unsigned char *r = Records[slot];
    memset(r, 0, 0x7BC);
    r[0] = 1;
    *(int *)(r + 0x08) = age;
    *(int *)(r + 0x0C) = sex;
    strncpy_s((char *)r + 0x18, 25, name, _TRUNCATE);
    *(int *)(r + 0x34) = head;
    *(int *)(r + 0x38) = body;
    *(int *)(r + 0xB4) = 90;
    *(int *)(r + 0xB8) = -1;
    *(int *)(r + 0xF4) = 44;
    *(int *)(r + 0xF8) = 55;
    *(int *)(r + 0x140) = 7;
    *(int *)(r + 0x144) = 2;
    r[0x150] = 3;
    *(unsigned *)(r + 0x7B8) = 0x19B;
}
static void Peep(int place, const char *name, int sex, int head, int body, int slot) {
    unsigned char *p = place == 0 ? Family + 4 : place == 1 ? Family + 0xDC : Family + 0x1B8 + (place - 2) * 0xD8;
    memset(p, 0, 0xD8);
    strncpy_s((char *)p, 25, name, _TRUNCATE);
    p[0x1A] = 1;
    *(int *)(p + 0x1C) = sex;
    *(int *)(p + 0x20) = head;
    *(int *)(p + 0x24) = body;
    *(int *)(p + 0x28) = slot;
    strncpy_s((char *)p + 0x34, 40, "reading", _TRUNCATE);
    if (place >= 2 && *(int *)(Family + 0x1B4) < place - 1) *(int *)(Family + 0x1B4) = place - 1;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    strncpy_s(Folder, argv[1], _TRUNCATE);
    for (int i = 0; i < 20; ++i) Vtable[i] = (void *)&StockLoad;
    Vtable[13] = (void *)&StockLoad;
    Vtable[14] = (void *)&StockSave;
    char dll[MAX_PATH];
    GetModuleFileNameA(0, dll, MAX_PATH);
    char *cut = strrchr(dll, '\\');
    strcpy_s(cut + 1, MAX_PATH - (cut + 1 - dll), "vf2revive_b200.dll");
    HMODULE m = LoadLibraryA(dll);
    if (!m) { printf("noload\n"); return 3; }
    typedef void (__cdecl *StartupFn)(const VF2ReviveHost *);
    typedef void (__cdecl *DeathFn)(int);
    typedef int (__cdecl *CandsFn)(Candidate *, int);
    typedef void (__cdecl *DoneFn)(int, int, int, const char *);
    typedef int (__cdecl *MembersFn)(Member *, int);
    MembersFn members = (MembersFn)GetProcAddress(m, "B200Revive_Members");
    StartupFn startup = (StartupFn)GetProcAddress(m, "B200Revive_Startup");
    DeathFn death = (DeathFn)GetProcAddress(m, "B200Revive_OnDeath");
    CandsFn cands = (CandsFn)GetProcAddress(m, "B200Revive_Candidates");
    DoneFn done = (DoneFn)GetProcAddress(m, "B200Revive_Done");
    volatile Status *status = (volatile Status *)GetProcAddress(m, "B200Revive_Status");
    if (!startup || !death || !cands || !done || !status || !members) { printf("noexports\n"); return 4; }
    volatile int *given = 0;
    volatile int *forgot = 0;
    static VF2ReviveHost host = { 0x31485652u, 1, sizeof(VF2ReviveHost), SaveRecord, SavePath, CurrentSlot,
                                  CurrentFamily, Generations, Vtable, (void *)&StockLoad, (void *)&StockSave };
    int a = 2;
    if (a < argc && !strcmp(argv[a], "hostbad")) { host.magic = 0; ++a; }
    if (a < argc && !strcmp(argv[a], "skin")) {          // the Skin Tones stand-in, loaded before the deaths
        strcpy_s(cut + 1, MAX_PATH - (cut + 1 - dll), "vf2skin_b200.dll");
        HMODULE s = LoadLibraryA(dll);
        given = s ? (volatile int *)GetProcAddress(s, "B200SkinStandin_Given") : 0;
        printf("skin %d\n", given ? 1 : 0);
        ++a;
    }
    if (a < argc && !strcmp(argv[a], "history")) {       // the Family History stand-in, loaded before the deaths
        strcpy_s(cut + 1, MAX_PATH - (cut + 1 - dll), "vf2history_b200.dll");
        HMODULE s = LoadLibraryA(dll);
        forgot = s ? (volatile int *)GetProcAddress(s, "B200HistoryStandin_Revived") : 0;
        printf("history %d\n", forgot ? 1 : 0);
        ++a;
    }
    startup(&host);
    printf("installed %u\n", status->installed);
    for (; a < argc; ++a) {
        const char *c = argv[a];
        if (!strcmp(c, "family")) {
            memset(Records, 0, sizeof(Records));
            memset(Family, 0, sizeof(Family));
            Family[0] = 1;
            Villager(0, "Ann", 1, 1, 1, 900); Villager(1, "Bob", 0, 2, 2, 950);
            Villager(2, "Cal", 0, 4, 4, 200); Villager(3, "Fay", 1, 9, 9, 60);
            Peep(0, "Ann", 1, 1, 1, 0); Peep(1, "Bob", 0, 2, 2, 1); Peep(2, "Cal", 0, 4, 4, 2); Peep(3, "Fay", 1, 9, 9, 3);
        } else if (!strcmp(c, "kill") && a + 2 < argc) {
            int s = atoi(argv[++a]);
            *(int *)(Records[s] + 0xB4) = 0;
            *(int *)(Records[s] + 0xB8) = atoi(argv[++a]);
            death(s);
        } else if (!strcmp(c, "gone") && a + 1 < argc) {           // ReportDeath: the tree's slot -1, inactive
            int s = atoi(argv[++a]);
            Records[s][0] = 0;
            for (int place = 0; place < 8; ++place) {
                unsigned char *p = place == 0 ? Family + 4 : place == 1 ? Family + 0xDC : Family + 0x1B8 + (place - 2) * 0xD8;
                if (p[0x1A] && *(int *)(p + 0x28) == s) *(int *)(p + 0x28) = -1;
            }
        } else if (!strcmp(c, "age") && a + 2 < argc) {
            int s = atoi(argv[++a]);
            *(int *)(Records[s] + 0x08) = atoi(argv[++a]);
        } else if (!strcmp(c, "reuse") && a + 1 < argc) {         // a new villager in the slot
            Villager(atoi(argv[++a]), "New", 0, 30, 30, 0);
        } else if (!strcmp(c, "load") && a + 1 < argc) {
            int n = atoi(argv[++a]);
            printf("load %d\n", ((SlotFn)Vtable[13])(GameState, 0, n) ? 1 : 0);
        } else if (!strcmp(c, "save") && a + 1 < argc) {
            int n = atoi(argv[++a]);
            Slot = n;
            printf("save %d\n", ((SlotFn)Vtable[14])(GameState, 0, n) ? 1 : 0);
        } else if (!strcmp(c, "cands")) {
            Candidate out[32];
            int n = cands(out, 32);
            printf("cands %d\n", n);
            for (int i = 0; i < n; ++i)
                printf("cand %d %s role %d age %d sex %d head %d body %d\n", out[i].index, out[i].name, out[i].role,
                       out[i].ageUnits, out[i].sex, out[i].head, out[i].body);
        } else if (!strcmp(c, "done") && a + 3 < argc) {
            int i = atoi(argv[++a]), s = atoi(argv[++a]);
            const char *role = argv[++a];
            Candidate out[32];
            int n = cands(out, 32);
            for (int k = 0; k < n; ++k) {
                if (out[k].index != i) continue;
                Villager(s, out[k].name, out[k].sex, out[k].head, out[k].body, out[k].ageUnits);
                done(i, s, out[k].ageUnits, role);
            }
        } else if (!strcmp(c, "members")) {
            Member out[8];
            int n = members(out, 8);
            printf("members %d\n", n);
            for (int i = 0; i < n; ++i)
                printf("member %s slot %d sex %d head %d body %d\n", out[i].name, out[i].slot, out[i].sex,
                       out[i].head, out[i].body);
        } else if (!strcmp(c, "forgot")) {
            if (forgot) printf("forgot %d slot %d\n", forgot[0], forgot[1]);
        } else if (!strcmp(c, "given")) {
            if (given) printf("given %d slot %d tone %d birth %d\n", given[0], given[1], given[2], given[3]);
        } else if (!strcmp(c, "remarry")) {                         // a new spouse in parent 2's place
            Villager(9, "Hal", 0, 6, 6, 800);
            Peep(1, "Hal", 0, 6, 6, 9);
        } else if (!strcmp(c, "status")) {
            printf("status installed %u entries %u captures %u load %u save %u revived %u\n", status->installed,
                   status->entries, status->captures, status->lastLoad, status->lastSave, status->revived);
        } else if (!strcmp(c, "vtable")) {
            printf("vtable %d %d\n", Vtable[13] == (void *)&StockLoad ? 0 : 1, Vtable[14] == (void *)&StockSave ? 0 : 1);
        }
    }
    return 0;
}
