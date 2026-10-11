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
