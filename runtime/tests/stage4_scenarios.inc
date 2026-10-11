// Stage 4 harness scenarios (included by stage1_harness.cpp; NOT shipped).
//
// Same method as the earlier stages: the copied STOCK game code runs, and only
// the game's runtime calls (sound, dialogs, scene controls, the game-state
// singleton, the random numbers, ...) are replaced by recorders that append
// one short string per call to an event log. Each scenario prints one JSON row
// with the observable result, so the Python tests can compare the hooked image
// against the unhooked one and against a model of the B200 behaviour.

// ------------------------------------------------------------ event log
static char gEv[8000];
static int gEvLen, gEvCount;

static void Ev(const char *fmt, ...) {
    va_list a;
    va_start(a, fmt);
    gEvLen += _snprintf_s(gEv + gEvLen, sizeof gEv - gEvLen, _TRUNCATE, gEvCount ? ", \"" : "\"");
    gEvLen += _vsnprintf_s(gEv + gEvLen, sizeof gEv - gEvLen, _TRUNCATE, fmt, a);
    gEvLen += _snprintf_s(gEv + gEvLen, sizeof gEv - gEvLen, _TRUNCATE, "\"");
    va_end(a);
    gEvCount++;
}

static void EvReset() { gEvLen = 0; gEvCount = 0; gEv[0] = 0; }

// ------------------------------------------------------------ title menu fakes
static unsigned char gMenu[0x400];
static unsigned char gMenuState[0x26000];
static const unsigned kPlayBtn = 0x7200100, kManageBtn = 0x7200200, kNameBtn = 0x7200300;
static const unsigned kStrings = 0x7000003, kFont = 0x7000004, kAnimThis = 0x7200010;
static int gMsgResult, gModalResult;
static bool gPresent[16];

static const char *BtnName(void *p) {
    unsigned v = (unsigned)p;
    return v == kPlayBtn ? "play" : v == kManageBtn ? "manage" : v == kNameBtn ? "name" : "other";
}

static void __fastcall FSoundPlay(void *self, void *, int id) {  // ret 4
    Ev("sound %X%s", id, self == (void *)0x569DB0 ? "" : " BAD-THIS");
}
static int __cdecl FShowMessageBox(void *scene, int id, int zero, int flag) {
    Ev("msgbox %s %X %d %d", scene == gMenu ? "menu" : "BAD-SCENE", id, zero, flag & 0xFF);
    return gMsgResult;
}
static void __fastcall FGameStateInit(void *self, void *) {
    Ev("init %s speed=%d", self == gMenuState ? "state" : "BAD-STATE", *(int *)(gMenuState + 0x25B18));
    memset(gMenuState + 0x25ABC, 0xEE, 0x18);  // the real Init wipes the name
    *(int *)0x568018 = 0;                       // and GameStats[0]
}
static bool __fastcall FSaveCurrentGame(void *self, void *) {
    Ev("save %s", self == gMenuState ? "state" : "BAD-STATE");
    return true;
}
static void __fastcall FSetStory(void *, void *, int story) { Ev("setstory %d", story); }  // ret 4
static void __fastcall FNickCtor(void *, void *, int zero) { Ev("nick_ctor %d", zero); }   // ret 4
static int __fastcall FDoModal(void *, void *, void *scene, int zero) {                    // ret 8
    Ev("domodal %s %d", scene == gMenu ? "menu" : "BAD-SCENE", zero);
    return gModalResult;
}
static void __fastcall FNickDtor(void *, void *) { Ev("nick_dtor"); }
static void *__fastcall FGetControl(void *scene, void *, int id) {  // ret 4
    Ev("get %d%s", id, scene == gMenu ? "" : " BAD-SCENE");
    return id >= 0 && id < 16 && gPresent[id] ? (void *)(0x7300000 + id) : 0;
}
static void __fastcall FAddControl(void *scene, void *, void *control) {  // ret 4
    Ev("add %s%s", BtnName(control), scene == gMenu ? "" : " BAD-SCENE");
}
static void __fastcall FRemoveControl(void *scene, void *, void *control) {  // ret 4
    Ev("remove %s%s", BtnName(control), scene == gMenu ? "" : " BAD-SCENE");
}
static void __fastcall FNameSetText(void *button, void *, const char *text) {  // ret 4
    Ev("name_text %s %s", BtnName(button), text);
}
static void *__fastcall FTitleLargeFont(void *strings, void *) {
    Ev("font %s", strings == (void *)kStrings ? "strings" : "BAD-STRINGS");
    return (void *)kFont;
}
static const char *__fastcall FTitleGetString(void *strings, void *, int id) {  // ret 4
    Ev("string %X%s", id, strings == (void *)kStrings ? "" : " BAD-STRINGS");
    return id == 0x775 ? "Play" : id == 0x280 ? "Continue" : "?";
}
static void __fastcall FTitleSetText(void *button, void *, const char *text, unsigned c1, unsigned c2,
                                     unsigned c3, void *font) {  // ret 14h
    unsigned white = *(unsigned *)0x534BF4;
    Ev("settext %s %s %s %s", BtnName(button), text, c1 == white && c2 == white && c3 == white ? "white" : "BAD-COLOUR",
       font == (void *)kFont ? "font" : "BAD-FONT");
}
static void __fastcall FButterflies(void *self, void *) {
    Ev("butterflies %s", self == (void *)0x55F598 ? "ok" : "BAD-THIS");
}
static void __fastcall FAnimReset(void *self, void *) {
    Ev("anim %s", self == (void *)kAnimThis ? "ok" : "BAD-THIS");
}

static void InstallMenuFakes() {
    WriteJmp(0x446BC0, (void *)&FSoundPlay);
    WriteJmp(0x421410, (void *)&FShowMessageBox);
    WriteJmp(0x429DD0, (void *)&FGameStateInit);
    WriteJmp(0x429660, (void *)&FSaveCurrentGame);
    WriteJmp(0x4B5D90, (void *)&FSetStory);
    WriteJmp(0x41F640, (void *)&FNickCtor);
    WriteJmp(0x401B60, (void *)&FDoModal);
    WriteJmp(0x41F970, (void *)&FNickDtor);
    WriteJmp(0x40CFD0, (void *)&FGetControl);
    WriteJmp(0x40CF80, (void *)&FAddControl);
    WriteJmp(0x40D000, (void *)&FRemoveControl);
    WriteJmp(0x40E1D0, (void *)&FNameSetText);
    WriteJmp(0x448E80, (void *)&FTitleLargeFont);
    WriteJmp(0x448E90, (void *)&FTitleGetString);
    WriteJmp(0x4015E0, (void *)&FTitleSetText);
    WriteJmp(0x426BD0, (void *)&FButterflies);
    WriteJmp(0x42C020, (void *)&FAnimReset);
}

static void ResetMenu(int speed, int slot, int village) {
    memset(gMenu, 0, sizeof gMenu);
    memset(gMenuState, 0, sizeof gMenuState);
    *(void **)(gMenu + 0xC) = gMenuState;
    *(unsigned *)(gMenu + 0x10) = kAnimThis;
    *(unsigned *)(gMenu + 0x14) = kStrings;
    *(int *)(gMenu + 0xC0) = 1;   // Play
    *(int *)(gMenu + 0xC4) = 2;   // Manage Games
    *(int *)(gMenu + 0xC8) = 6;   // Start Over
    *(int *)(gMenu + 0xCC) = 3;
    *(int *)(gMenu + 0xD0) = 7;   // the player-name control
    *(int *)(gMenu + 0xD4) = 4;
    *(unsigned *)(gMenu + 0xD8) = kPlayBtn;
    *(unsigned *)(gMenu + 0xE4) = kManageBtn;
    *(unsigned *)(gMenu + 0xF0) = kNameBtn;
    *(int *)(gMenuState + 0x25B18) = speed;
    *(int *)(gMenuState + 0x25B20) = slot;
    *(int *)(gMenuState + 0x25CB8) = 5;   // story slot
    *(int *)(gMenuState + 0x25CBC) = 0x77;
    for (int i = 0; i < 0x18; ++i) gMenuState[0x25ABC + i] = (unsigned char)(0x41 + i);
    memcpy(gMenuState + 0x25ABC, "Alyssa", 7);
    *(int *)0x568018 = village;
    memset(gPresent, 0, sizeof gPresent);
    EvReset();
}

static void MenuHex(char *dst, const unsigned char *src, unsigned n) { Hex(dst, src, n); }

typedef bool (__thiscall *MenuHandleFn)(void *, int, long);
typedef void (__thiscall *MenuVoidFn)(void *);
typedef void (__thiscall *MenuBoolFn)(void *, bool);

static void PrintMenuRow(const char *kind, const char *name, int result, int espOk) {
    char nameHex[64];
    MenuHex(nameHex, gMenuState + 0x25ABC, 0x18);
    Out("{\"menu_case\": \"%s:%s\", \"result\": %d, \"esp_ok\": %d, \"speed\": %d, \"name\": \"%s\", "
        "\"story\": [%d, %d], \"slot\": %d, \"gs0\": %d, \"events\": [%s]}",
        kind, name, result, espOk, *(int *)(gMenuState + 0x25B18), nameHex, *(int *)(gMenuState + 0x25CB8),
        *(int *)(gMenuState + 0x25CBC), *(int *)(gMenuState + 0x25B20), *(int *)0x568018, gEv);
}

// Calls a thiscall function with the stack depth checked (esp before == after).
static int CallThis1(unsigned fn, void *self, int a, long b, int *espOk) {
    unsigned before = 0, after = 0;
    int result = 0;
    __asm {
        mov before, esp
        push b
        push a
        mov ecx, self
        mov eax, fn
        call eax
        movzx eax, al
        mov result, eax
        mov after, esp
    }
    *espOk = before == after ? 1 : 0;
    return result;
}

static void RunMenuScenarios() {
    InstallMenuFakes();

    // ---- Start Over / Play clicks through the copied theMenuScene::HandleMessage
    struct StartCase { const char *name; int id; int village; int answer; int speed; int slot; };
    static const StartCase starts[] = {
        { "start_over_no_village", 6, 0, 0, 10, 1 },
        { "start_over_no_village_no_slot", 6, 0, 0, 10, 0 },
        { "start_over_no", 6, 1, -1, 10, 1 },
        { "start_over_yes", 6, 1, 0, 10, 1 },
        { "start_over_yes_speed_998", 6, 1, 0, 998, 1 },
        { "start_over_yes_speed_999", 6, 1, 0, 999, 1 },
        { "start_over_yes_speed_1009", 6, 1, 0, 1009, 1 },
        { "play_village", 1, 1, -1, 10, 1 },
        { "play_no_village", 1, 0, -1, 10, 1 },
        { "unknown_button", 5, 1, -1, 10, 1 },
    };
    for (const StartCase &c : starts) {
        ResetMenu(c.speed, c.slot, c.village);
        gMsgResult = c.answer;
        gModalResult = 0;
        int espOk = 0;
        // The no-slot case reaches the name prompt, which this row answers OK.
        int r = CallThis1(0x443EF0, gMenu, 8, c.id, &espOk);
        PrintMenuRow("click", c.name, r, espOk);
    }

    // ---- the name prompt: OK and cancel (Play with no village and no player slot)
    for (int answer = -1; answer <= 0; ++answer) {
        ResetMenu(10, 0, 0);
        gPresent[7] = true;   // the name control is in the scene
        gPresent[2] = true;
        gModalResult = answer;
        int espOk = 0;
        int r = CallThis1(0x443EF0, gMenu, 8, 1, &espOk);
        PrintMenuRow("nickname", answer == -1 ? "cancel" : "ok", r, espOk);
    }
    for (int answer = -1; answer <= -1; ++answer) {
        ResetMenu(10, 0, 0);
        gPresent[7] = false;  // after the player was deleted: nothing of the old title is shown
        gPresent[2] = false;
        gModalResult = answer;
        int espOk = 0;
        int r = CallThis1(0x443EF0, gMenu, 8, 1, &espOk);
        PrintMenuRow("nickname", "cancel_nothing_shown", r, espOk);
    }

    // ---- UpdateShowPlayer (0x443B80) called directly, as its two stock callers do
    for (int village = 0; village < 2; ++village)
        for (int slot = 0; slot < 2; ++slot)
            for (int namePresent = 0; namePresent < 2; ++namePresent)
                for (int managePresent = 0; managePresent < 2; ++managePresent) {
                    ResetMenu(10, slot, village);
                    gPresent[7] = namePresent != 0;
                    gPresent[2] = managePresent != 0;
                    unsigned before = 0, after = 0;
                    __asm {
                        mov before, esp
                        mov ecx, offset gMenu
                        mov eax, 0x443B80
                        call eax
                        mov after, esp
                    }
                    char name[64];
                    _snprintf_s(name, sizeof name, _TRUNCATE, "village%d_slot%d_name%d_manage%d", village, slot,
                                namePresent, managePresent);
                    PrintMenuRow("update_show_player", name, 0, before == after ? 1 : 0);
                }

    // ---- Activate(bool), vtable slot 9 of theMenuScene (0x4439F0)
    for (int arg = 1; arg >= 0; --arg)
        for (int village = 0; village < 2; ++village) {
            ResetMenu(10, 1, village);
            gPresent[7] = false;
            gPresent[2] = false;
            unsigned before = 0, after = 0;
            __asm {
                mov before, esp
                movzx eax, arg
                push eax
                mov ecx, offset gMenu
                mov eax, 0x4439F0
                call eax
                mov after, esp
            }
            char name[64];
            _snprintf_s(name, sizeof name, _TRUNCATE, "arg%d_village%d", arg, village);
            PrintMenuRow("activate", name, 0, before == after ? 1 : 0);
        }
    *(int *)0x568018 = 0;
}

// ------------------------------------------------------------ older_villager_mortality
// The stock old-age statement (0x49BBBD..0x49BC46) is run from its first byte
// to its exit (0x49BC47) with a CVillagerState in ebp and the loop pointer in
// esi, exactly as CVillagerManager::AllVillagersRealtimePhysiologyAndProduc-
// tivityUpkeep has them. FoodGroupsActive and SetHealth are recorders; the
// random numbers are the harness's GetRandom. The stack is padded because the
// stock statement keeps a local at [esp+0x20].
static int gFgReturn, gFgCalls, gFgArg;
static void *gFgThis;
static int __fastcall FFoodGroupsActive(void *self, void *, int arg) {  // ret 4
    gFgCalls++; gFgArg = arg; gFgThis = self;
    return gFgReturn;
}
static int gHealthCalls, gHealthA, gHealthB;
static void *gHealthThis;
static void __fastcall FSetHealth(void *self, void *, int health, int cause) {  // ret 8
    gHealthCalls++; gHealthA = health; gHealthB = cause; gHealthThis = self;
}

static __declspec(naked) void RunSpanPadded() {
    __asm {
        pushad
        pushfd
        mov gSaveEsp, esp
        sub esp, 0x200
        mov gArriveEsp, esp
        push in_flags
        popfd
        mov eax, in_eax
        mov ebx, in_ebx
        mov ecx, in_ecx
        mov edx, in_edx
        mov esi, in_esi
        mov edi, in_edi
        mov ebp, in_ebp
        jmp dword ptr [gCooldownSite]
    }
}

static unsigned char gMortalityBuffer[0x20000];

// One run of the statement. Returns 1 when SetHealth was called.
static int RunMortalityOnce(int age, int groups, int random, unsigned *flags) {
    unsigned char *state = gMortalityBuffer + 0x100;
    *(int *)(state + 8) = age;
    gFgReturn = groups;
    gFgCalls = gHealthCalls = gRandomCalls = 0;
    gFgArg = gHealthA = gHealthB = -7;
    gFgThis = gHealthThis = 0;
    gRandomValue = random;
    gRandomLimit = 0;
    in_eax = 0xA0A0A0A0; in_ebx = 0xB0B0B0B0; in_ecx = 0xC0C0C0C0; in_edx = 0xD0D0D0D0;
    in_esi = (unsigned)state + 0x15094; in_edi = 0xE0E0E0E0; in_ebp = (unsigned)state; in_flags = 0x2;
    gCooldownSite = 0x49BBBD;
    out_esp = 0;
    RunSpanPadded();
    if (flags) {
        *flags = (out_esp == gArriveEsp ? 1u : 0u) | (out_ebp == in_ebp ? 2u : 0u) | (out_esi == in_esi ? 4u : 0u) |
                 (gHealthCalls == 0 || (gHealthThis == state && gHealthA == 0 && gHealthB == 2) ? 8u : 0u) |
                 (gFgCalls == 0 || gFgThis == state ? 16u : 0u);
    }
    return gHealthCalls;
}

static void RunMortalityScenarios() {
    WriteJmp(0x4A0A80, (void *)&FFoodGroupsActive);
    WriteJmp(0x4A0420, (void *)&FSetHealth);
    WriteJmp(0x49BC47, (void *)&CooldownResumeCapture);  // the statement's exit
    static char rows[400000];
    for (int groups = 0; groups <= 5; ++groups) {
        int len = 0;
        // Whole birthdays from 0 to 330 years, plus ages between birthdays.
        for (int step = 0; step <= 331 + 6; ++step) {
            int age = step <= 331 ? step * 20 : 1100 + (step - 332) * 7 + 1;
            unsigned flags = 0;
            int killedAtZero = RunMortalityOnce(age, groups, 0, &flags);
            int calls = gRandomCalls, limit = gRandomLimit, fga = gFgCalls, fgArg = gFgArg;
            int threshold = 0;
            if (calls) {
                // kill(r) is monotone: killed below a threshold, not above.
                if (killedAtZero) {
                    int lo = 0, hi = 1000001;  // lo kills; hi does not
                    unsigned f2 = 0;
                    if (RunMortalityOnce(age, groups, 1000000, &f2)) lo = 1000000;
                    while (hi - lo > 1 && lo != 1000000) {
                        int mid = (lo + hi) / 2;
                        unsigned f3 = 0;
                        if (RunMortalityOnce(age, groups, mid, &f3)) lo = mid; else hi = mid;
                        flags &= f3;
                    }
                    threshold = lo + 1;
                    flags &= f2;
                }
            }
            len += _snprintf_s(rows + len, sizeof rows - len, _TRUNCATE, "%s[%d, %d, %d, %d, %d, %d, %u]",
                               step ? ", " : "", age, calls, limit, threshold, fga, fgArg, flags);
        }
        Out("{\"mortality\": %d, \"rows\": [%s]}", groups, rows);
    }
}

// ------------------------------------------------------------ event_collectable_slot_replacement
// The three patched `call Add` sites are reached through the copied stock
// event code (CEventTheNeighborCollectible::ImpactGame, CEventTheBugWhisperer::
// ImpactGame) and through the thunk each rel32 now points at. The native Add
// runs for real when the carrying is explicit (the Bug Whisperer path) and is
// a recorder for the random-carrying path (Neighbor Collectible), which needs
// the game world; the recorder either activates a slot the way the native tail
// does or gives up like the native random path can.
static unsigned char gOriginalAdd[5];
static int gAddMode;   // 0: the real native Add; 1: recorder that activates; 2: recorder that gives up
static int gAddFakeCalls;
static void __fastcall FakeCollectableAdd(void *item, void *, int carrying, int x, int y, int force) {  // ret 10h
    gAddFakeCalls++;
    if (gAddMode != 1) return;
    unsigned char *base = (unsigned char *)0x55A620 + 0x34C;
    int slot = 0;
    while (slot < 2 && base[slot * 0x1C] && !(force & 0xFF)) slot++;
    if (slot == 2) return;
    unsigned char *s = base + slot * 0x1C;
    s[0] = 1;
    *(int *)(s + 4) = carrying;
    *(unsigned *)(s + 8) = gClock + 0x78;
    *(int *)(s + 0xC) = x;
    *(int *)(s + 0x10) = y;
    *(int *)(s + 0x14) = -1;
}
static void __fastcall FakeBugWhispererTimer(void *, void *, float, int) {}  // 0x428050, ret 8

static void CollectableSelectMode(int mode) {
    DWORD old;
    if (mode == 0) {
        VirtualProtect((void *)0x415090, 5, PAGE_EXECUTE_READWRITE, &old);
        memcpy((void *)0x415090, gOriginalAdd, 5);
        VirtualProtect((void *)0x415090, 5, old, &old);
        FlushInstructionCache(GetCurrentProcess(), (void *)0x415090, 5);
    } else {
        WriteJmp(0x415090, (void *)&FakeCollectableAdd);
    }
    gAddMode = mode;
}

struct CSlot { int active; int carrying; unsigned stamp; int x; int y; int picked; };

static void SetCollectSlot(int slot, const CSlot &c) {
    unsigned char *s = (unsigned char *)0x55A620 + 0x34C + slot * 0x1C;
    memset(s, 0, 0x1C);
    s[0] = (unsigned char)c.active;
    *(int *)(s + 4) = c.carrying;
    *(unsigned *)(s + 8) = c.stamp;
    *(int *)(s + 0xC) = c.x;
    *(int *)(s + 0x10) = c.y;
    *(int *)(s + 0x14) = c.picked;
}

static int SlotsJson(char *dst, int cap) {
    int len = 0;
    len += _snprintf_s(dst + len, cap - len, _TRUNCATE, "[");
    for (int slot = 0; slot < 2; ++slot) {
        unsigned char *s = (unsigned char *)0x55A620 + 0x34C + slot * 0x1C;
        len += _snprintf_s(dst + len, cap - len, _TRUNCATE, "%s[%d, %d, %u, %d, %d, %d]", slot ? ", " : "", s[0],
                           *(int *)(s + 4), *(unsigned *)(s + 8), *(int *)(s + 0xC), *(int *)(s + 0x10),
                           *(int *)(s + 0x14));
    }
    len += _snprintf_s(dst + len, cap - len, _TRUNCATE, "]");
    return len;
}

static int CallAddThunk(unsigned thunk, int carrying, int x, int y, int force) {
    unsigned before = 0, after = 0;
    __asm {
        mov before, esp
        push force
        push y
        push x
        push carrying
        mov ecx, 0x55A620
        mov eax, thunk
        call eax
        mov after, esp
    }
    return before == after ? 1 : 0;
}

static void PrintCollectRow(const char *kind, const char *name, int clock, const char *in, int a, int b, int c, int d,
                            int espOk) {
    char out[400];
    SlotsJson(out, sizeof out);
    Out("{\"collect\": \"%s:%s\", \"mode\": %d, \"clock\": %d, \"op\": [%d, %d, %d, %d], \"in\": %s, \"out\": %s, "
        "\"esp_ok\": %d, \"fake_calls\": %d}",
        kind, name, gAddMode, clock, a, b, c, d, in, out, espOk, gAddFakeCalls);
}

static CSlot CollectKind(int slot, int kind, unsigned now) {
    unsigned stamp = now + 0x78;
    CSlot c = { 1, 0x60 + slot * 8 + kind, 0, 11 + slot, 22 + slot, -1 };
    switch (kind) {
    case 0: c.active = 0; c.carrying = 0; c.x = c.y = 0; break;               // free
    case 1: c.stamp = stamp - 50; break;                                      // unpicked, older
    case 2: c.stamp = stamp - 10; break;                                      // unpicked, newer
    case 3: c.stamp = stamp - 50; c.picked = 5; break;                        // picked, older
    case 4: c.stamp = stamp - 10; c.picked = 5; break;                        // picked, newer
    case 5: c.stamp = stamp; break;                                           // unpicked, stamped this very second
    }
    return c;
}

static void RunCollectableScenarios() {
    memcpy(gOriginalAdd, (void *)0x415090, 5);
    static unsigned char scratchState[0x26000];
    *(unsigned char **)0x558FC0 = scratchState;   // theGameState::Get()
    WriteJmp(0x403FF0, (void *)&FakeSeconds);     // the game clock
    WriteJmp(0x428050, (void *)&FakeBugWhispererTimer);
    unsigned thunk = 0x41AF0E + 5 + *(int *)(0x41AF0E + 1);
    unsigned thunkNeighbor = 0x419A2F + 5 + *(int *)(0x419A2F + 1);
    unsigned thunk2 = 0x41AF4B + 5 + *(int *)(0x41AF4B + 1);
    Out("{\"collect_targets\": [%u, %u, %u]}", thunkNeighbor, thunk, thunk2);
    char in[400];
    const int T = 5000;

    // ---- plain (explicit carrying) adds through the thunk, the real native Add
    CollectableSelectMode(0);
    for (int prior = 0; prior < 3; ++prior)
        for (int k0 = 0; k0 < 6; ++k0)
            for (int k1 = 0; k1 < 6; ++k1)
                for (int force = 0; force < 2; ++force) {
                    gClock = T;
                    SetCollectSlot(0, CollectKind(0, 0, T));
                    SetCollectSlot(1, CollectKind(1, 0, T));
                    if (prior == 2) SetCollectSlot(0, CollectKind(0, 1, T));
                    if (prior) {
                        SlotsJson(in, sizeof in);
                        int ok = CallAddThunk(thunk, 0x70 + prior, 5, 6, 0);
                        PrintCollectRow("prior", "burst", T, in, 0x70 + prior, 5, 6, 0, ok);
                    }
                    // Keep the slot the prior spawn landed in when its kind is "stamped this second".
                    unsigned char saved[2][0x1C];
                    memcpy(saved[0], (void *)(0x55A620 + 0x34C), 0x1C);
                    memcpy(saved[1], (void *)(0x55A620 + 0x34C + 0x1C), 0x1C);
                    int landed = prior == 1 ? 0 : prior == 2 ? 1 : -1;
                    if (!(landed == 0 && k0 == 5)) SetCollectSlot(0, CollectKind(0, k0, T));
                    else memcpy((void *)(0x55A620 + 0x34C), saved[0], 0x1C);
                    if (!(landed == 1 && k1 == 5)) SetCollectSlot(1, CollectKind(1, k1, T));
                    else memcpy((void *)(0x55A620 + 0x34C + 0x1C), saved[1], 0x1C);
                    SlotsJson(in, sizeof in);
                    int ok = CallAddThunk(thunk, 0x55, 7, 9, force);
                    char name[64];
                    _snprintf_s(name, sizeof name, _TRUNCATE, "p%d_k%d%d_f%d", prior, k0, k1, force);
                    PrintCollectRow("add", name, T, in, 0x55, 7, 9, force, ok);
                }

    // ---- a burst whose stamp is no longer "this second"
    {
        gClock = T;
        SetCollectSlot(0, CollectKind(0, 0, T));
        SetCollectSlot(1, CollectKind(1, 0, T));
        SlotsJson(in, sizeof in);
        int ok = CallAddThunk(thunk, 0x71, 1, 2, 0);
        PrintCollectRow("prior", "stale_burst", T, in, 0x71, 1, 2, 0, ok);
        SetCollectSlot(1, CollectKind(1, 1, T));
        gClock = T + 200;                                       // the burst is over
        SlotsJson(in, sizeof in);
        ok = CallAddThunk(thunk, 0x72, 3, 4, 0);
        PrintCollectRow("add", "stale_burst", T + 200, in, 0x72, 3, 4, 0, ok);
    }

    // ---- the Bug Whisperer event itself (two Adds, explicit carrying, the real native Add)
    for (int arg = 0; arg < 2; ++arg)
        for (int k0 = 0; k0 < 5; ++k0)
            for (int k1 = 0; k1 < 5; k1 += (k0 == 0 ? 1 : 2)) {
                gClock = T;
                gRandomValue = 3;
                SetCollectSlot(0, CollectKind(0, k0, T));
                SetCollectSlot(1, CollectKind(1, k1, T));
                SlotsJson(in, sizeof in);
                unsigned before = 0, after = 0;
                __asm {
                    mov before, esp
                    push arg
                    mov ecx, 0x5680C8
                    mov eax, 0x41AE90
                    call eax
                    mov after, esp
                }
                char name[64];
                _snprintf_s(name, sizeof name, _TRUNCATE, "arg%d_k%d%d", arg, k0, k1);
                PrintCollectRow("bug_whisperer", name, T, in, 3, 0, 0, arg, before == after ? 1 : 0);
            }

    // ---- the Neighbor Collectible event (random carrying, forced): a recorder as the native Add
    for (int mode = 1; mode <= 2; ++mode) {
        CollectableSelectMode(mode);
        for (int k0 = 0; k0 < 6; ++k0)
            for (int k1 = 0; k1 < 6; ++k1) {
                gClock = T;
                gAddFakeCalls = 0;
                SetCollectSlot(0, CollectKind(0, k0, T));
                SetCollectSlot(1, CollectKind(1, k1, T));
                SlotsJson(in, sizeof in);
                unsigned before = 0, after = 0;
                __asm {
                    mov before, esp
                    mov ecx, offset gMenu
                    mov eax, 0x419A20
                    call eax
                    mov after, esp
                }
                char name[64];
                _snprintf_s(name, sizeof name, _TRUNCATE, "m%d_k%d%d", mode, k0, k1);
                PrintCollectRow("neighbor", name, T, in, -1, 0, 0, 1, before == after ? 1 : 0);
            }
    }
    CollectableSelectMode(0);
    for (int slot = 0; slot < 2; ++slot) SetCollectSlot(slot, CollectKind(slot, 0, T));
    *(unsigned char **)0x558FC0 = 0;
}
