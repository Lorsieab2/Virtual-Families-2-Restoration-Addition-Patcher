// b200time_time.inc -- the Time Controls module; included by b200time.cpp after
// the site table (SITE), the resolver and the plan type.
//
// Adapted from the REDUX runtime-hook build's vf2fun_time.inc (Settings-screen version; a separate branch)
// for the B200 executable: every address is found in the live image by the resolver and read through
// SITE(), the Settings button is built at x = 30 / id 9, and the aging hook is a
// retargeted `call IncrementAge` instead of a 5-byte stolen run (B200 saves the
// native tick count itself, so no register juggling is needed).

// ---------------------------------------------------------------- game ABI
struct ldwPoint { int x, y; };

typedef void (__thiscall *SetSpeedFn)(void *time, int speed);
typedef void *(__cdecl *NewFn)(size_t size);
typedef void *(__cdecl *GetManagerFn)();
typedef void *(__thiscall *GetImageGridFn)(void *graphics, int image);
typedef void *(__thiscall *ButtonCtorFn)(void *self, int id, void *grid, ldwPoint pos, void *scene, bool flag);
typedef void (__thiscall *ButtonSetTextFn)(void *self, const char *text, unsigned c1, unsigned c2,
                                           unsigned c3, void *font);
typedef void (__thiscall *AddControlFn)(void *scene, void *control);
typedef int (__thiscall *ControlSizeFn)(void *control);
typedef void *(__thiscall *GetEvictFontFn)(void *strings);
typedef bool (__thiscall *HandleMessageFn)(void *scene, int message, long param);
typedef void (__thiscall *IncrementAgeFn)(int *age, int ticks);
typedef bool (__thiscall *GameStateSlotFn)(void *state, int slot);

// Resolved from the live module base by ResolveAbi() before anything is planned.
static SetSpeedFn SetSpeed;
static void *GameTime;
static NewFn GameNew;
static GetManagerFn GraphicsGet;
static GetImageGridFn GetImageGrid;
static GetEvictFontFn GetEvictFont;
static ButtonCtorFn ButtonCtor;
static ButtonSetTextFn ButtonSetText;
static AddControlFn AddControl;
static HandleMessageFn NativeOptionsHandleMessage;
static IncrementAgeFn NativeIncrementAge;
static GameStateSlotFn NativeGameStateSave;
static GameStateSlotFn NativeGameStateLoad;
static unsigned NativeSetChecked;       // read by the naked constructor stub
static unsigned char **GameStatePtr;
static unsigned VillagerBase;           // first villager's age field: manager + array + age offset

static void ResolveAbi() {
    SetSpeed = (SetSpeedFn)SITE(SET_SPEED);
    GameTime = (void *)SITE(GAME_TIME);
    GameNew = (NewFn)SITE(GAME_NEW);
    GraphicsGet = (GetManagerFn)SITE(GRAPHICS_GET);
    GetImageGrid = (GetImageGridFn)SITE(GRAPHICS_GET_IMAGE_GRID);
    GetEvictFont = (GetEvictFontFn)SITE(GET_EVICT_FONT);
    ButtonCtor = (ButtonCtorFn)SITE(BUTTON_CTOR);
    ButtonSetText = (ButtonSetTextFn)SITE(BUTTON_SET_TEXT);
    AddControl = (AddControlFn)SITE(SCENE_ADD_CONTROL);
    NativeOptionsHandleMessage = (HandleMessageFn)SITE(OPTIONS_HANDLE_MESSAGE);
    NativeIncrementAge = (IncrementAgeFn)SITE(INCREMENT_AGE);
    NativeGameStateSave = (GameStateSlotFn)SITE(GAME_STATE_SAVE);
    NativeGameStateLoad = (GameStateSlotFn)SITE(GAME_STATE_LOAD);
    NativeSetChecked = SITE(CONTROL_SET_CHECKED);
    GameStatePtr = (unsigned char **)SITE(GAME_STATE_INSTANCE_PTR);
    VillagerBase = SITE(VILLAGER_MANAGER) + B200TC_VILLAGER_ARRAY_OFFSET + B200TC_VILLAGER_AGE_OFFSET;
}

static const int kTimeButtonId = B200TC_TIME_BUTTON_ID;
static const char kTimeButtonText[] = "Time Controls";

static unsigned char *VillagerByIndex(int index) {
    if (index < 0 || index >= 30) return 0;
    return (unsigned char *)(SITE(VILLAGER_MANAGER) + B200TC_VILLAGER_ARRAY_OFFSET +
                             (unsigned)index * B200TC_VILLAGER_STRIDE);
}

// ---------------------------------------------------------------- pause and speed
// theGameState keeps the speed in one int (+0x25B18). 20 is slow, 10 normal,
// 5 fast (2x), 2 is 5x, 1 is 10x. The Space key pauses by SetSpeed(999) and adding 999 to
// the field, and resumes by SetSpeed(field - 999) and storing that, so the
// speed to come back to rides along as the part below 999. These do the same.
static int *SpeedField() {
    unsigned char *state = *GameStatePtr;
    return state ? (int *)(state + B200TC_GAME_STATE_SPEED_FIELD) : 0;
}

static bool GamePaused() {
    int *field = SpeedField();
    return field && *field >= (int)B200TC_PAUSED_OFFSET;
}

// The speed the game runs at when not paused.
static int UnderlyingSpeed() {
    int *field = SpeedField();
    if (!field) return B200TC_SPEED_NORMAL;
    int speed = *field >= (int)B200TC_PAUSED_OFFSET ? *field - (int)B200TC_PAUSED_OFFSET : *field;
    return speed > 0 ? speed : B200TC_SPEED_NORMAL;
}

static void PauseGame() {
    int *field = SpeedField();
    if (!field || *field >= (int)B200TC_PAUSED_OFFSET) return;
    SetSpeed(GameTime, B200TC_PAUSED_OFFSET);
    *field += B200TC_PAUSED_OFFSET;
}

// Stock Space does SetSpeed(10) when the field is exactly 999; the speed is
// normal then, as in the Options dialog.
static void ResumeGame() {
    int *field = SpeedField();
    if (!field || *field < (int)B200TC_PAUSED_OFFSET) return;
    int speed = *field - (int)B200TC_PAUSED_OFFSET;
    if (speed <= 0) speed = B200TC_SPEED_NORMAL;
    SetSpeed(GameTime, speed);
    *field = speed;
}

static void ChooseSpeed(int speed) {
    int *field = SpeedField();
    if (!field) return;
    if (*field >= (int)B200TC_PAUSED_OFFSET) {
        *field = (int)B200TC_PAUSED_OFFSET + speed;  // stays paused; Resume restores this speed
        return;
    }
    SetSpeed(GameTime, speed);
    *field = speed;
}

// ---------------------------------------------------------------- time warp
static int WarpTicks;        // ticks each pending villager still gets
static unsigned WarpPending; // bit i: villager i has not yet been given them

static bool Eligible(int index) {
    const unsigned char *v = VillagerByIndex(index);
    return v && v[B200TC_VILLAGER_ACTIVE_OFFSET] && !v[B200TC_VILLAGER_LEFT_HOME_OFFSET] &&
           *(const int *)(v + B200TC_VILLAGER_HEALTH_OFFSET) > 0;
}

// Everyone at home and alive now gets `ticks` extra age ticks.
static void StartTimeWarp(int ticks) {
    WarpPending = 0;
    for (int i = 0; i < 30; ++i)
        if (Eligible(i)) WarpPending |= 1u << i;
    WarpTicks = WarpPending ? ticks : 0;
}

// True while someone is still waiting for the ticks. A villager who died or
// left home since cannot receive them (the game skips those), so is dropped.
static bool WarpUnderWay() {
    for (int i = 0; i < 30; ++i)
        if ((WarpPending & (1u << i)) && !Eligible(i)) WarpPending &= ~(1u << i);
    if (!WarpPending) WarpTicks = 0;
    return WarpPending != 0;
}

// The ticks IncrementAge is given for the villager whose age field is `age`.
static int WarpTicksFor(const int *age, int ticks) {
    if (!WarpTicks) return ticks;
    unsigned offset = (unsigned)age - VillagerBase;
    if (offset % B200TC_VILLAGER_STRIDE != 0 || offset / B200TC_VILLAGER_STRIDE >= 30) return ticks;
    unsigned bit = 1u << (offset / B200TC_VILLAGER_STRIDE);
    if (!(WarpPending & bit)) return ticks;
    WarpPending &= ~bit;
    int warp = WarpTicks;
    if (!WarpPending) WarpTicks = 0;
    return ticks + warp;
}

// Replaces the call to CVillagerBio::IncrementAge(int) inside
// AllVillagersTimeflowUpkeep (thiscall: ecx = &age, one stack argument, ret 4).
// __fastcall with a dummy EDX has the same ABI. The game keeps the NATIVE tick
// count in [ebp-14h] for the accumulator remainder, so only the age is affected.
static void __fastcall IncrementAgeWithWarp(int *age, void *, int ticks) {
    NativeIncrementAge(age, WarpTicksFor(age, ticks));
}

// ---------------------------------------------------------------- save and load
// theGameState::Save / Load (int slot), thiscall, ret 4, bool. Slot 0 is the
// player header only (+0x25B20, not the speed); every other slot carries the
// speed field and CGameTime's saved speed.

// The only values the stock game ever stores: normal, and normal while paused.
static bool StockSpeedValue(int field) {
    return field == (int)B200TC_SPEED_NORMAL || field == (int)(B200TC_PAUSED_OFFSET + B200TC_SPEED_NORMAL);
}

static bool __fastcall GameStateSaveSlot(void *state, void *, int slot) {
    int *field = state && slot ? (int *)((unsigned char *)state + B200TC_GAME_STATE_SPEED_FIELD) : 0;
    int live = field ? *field : (int)B200TC_SPEED_NORMAL;
    if (!field || StockSpeedValue(live)) return NativeGameStateSave(state, slot);
    bool paused = live >= (int)B200TC_PAUSED_OFFSET;
    // CGameTime saves its own speed too: rebase it to normal (the game's own
    // SetSpeed, as a speed change does) so the save is a normal-speed save.
    bool running = !paused && live > 0;
    if (running) SetSpeed(GameTime, B200TC_SPEED_NORMAL);
    *field = paused ? (int)(B200TC_PAUSED_OFFSET + B200TC_SPEED_NORMAL) : (int)B200TC_SPEED_NORMAL;
    bool ok = NativeGameStateSave(state, slot);
    if (running) SetSpeed(GameTime, live);
    *field = live;
    return ok;
}

static bool __fastcall GameStateLoadSlot(void *state, void *, int slot) {
    bool ok = NativeGameStateLoad(state, slot);
    if (!ok || !slot || !state) return ok;
    // A different village (or the same one, later): no queued warp carries over.
    WarpPending = 0;
    WarpTicks = 0;
    int *field = (int *)((unsigned char *)state + B200TC_GAME_STATE_SPEED_FIELD);
    if (StockSpeedValue(*field)) return ok;
    if (*field >= (int)B200TC_PAUSED_OFFSET) {
        *field = (int)(B200TC_PAUSED_OFFSET + B200TC_SPEED_NORMAL);  // stays paused; Resume runs at normal
    } else {
        *field = B200TC_SPEED_NORMAL;
        SetSpeed(GameTime, B200TC_SPEED_NORMAL);
    }
    return ok;
}

// ---------------------------------------------------------------- the dialog
// Built in memory (no resource script), like the Virtual Families 1 patcher's.
class Template {
    __declspec(align(4)) WORD buf[4096];
    int n;
    void Str(const wchar_t *s) { do buf[n++] = *s; while (*s++); }
public:
    DLGTEMPLATE *Begin(const wchar_t *title, int w, int h, int count) {
        n = 0;
        DLGTEMPLATE *t = (DLGTEMPLATE *)buf;
        t->style = DS_MODALFRAME | DS_CENTER | DS_SETFONT | WS_POPUP | WS_CAPTION | WS_SYSMENU;
        t->dwExtendedStyle = 0;
        t->cdit = (WORD)count;
        t->x = 0; t->y = 0; t->cx = (short)w; t->cy = (short)h;
        n = sizeof(DLGTEMPLATE) / 2;
        buf[n++] = 0; buf[n++] = 0;  // no menu, default class
        Str(title);
        buf[n++] = 9;                // point size
        Str(L"Segoe UI");
        return t;
    }
    void Item(WORD cls, DWORD style, int x, int y, int w, int h, int id, const wchar_t *text) {
        if (n % 2) buf[n++] = 0;  // DLGITEMTEMPLATE is DWORD aligned (n counts WORDs)
        DLGITEMTEMPLATE *it = (DLGITEMTEMPLATE *)(buf + n);
        it->style = style | WS_CHILD | WS_VISIBLE;
        it->dwExtendedStyle = 0;
        it->x = (short)x; it->y = (short)y; it->cx = (short)w; it->cy = (short)h;
        it->id = (WORD)id;
        n += sizeof(DLGITEMTEMPLATE) / 2;
        buf[n++] = 0xFFFF; buf[n++] = cls;
        Str(text);
        buf[n++] = 0;  // no creation data
    }
    DLGTEMPLATE *Get() { return (DLGTEMPLATE *)buf; }
};

enum { BUTTON = 0x80, STATIC = 0x82 };

// While the dialog is open the game leaves fullscreen so it cannot end up
// hidden behind the game; the exact fullscreen mode is restored afterwards.
// Uses the game's own SDL2.dll.
class LeaveFullscreen {
    typedef void *(__cdecl *GetWindowFn)();
    typedef unsigned (__cdecl *GetFlagsFn)(void *);
    typedef int (__cdecl *SetFullscreenFn)(void *, unsigned);
    void *window;
    unsigned mode;
    SetFullscreenFn setFullscreen;
public:
    LeaveFullscreen() : window(0), mode(0), setFullscreen(0) {
        HMODULE sdl = GetModuleHandleW(L"SDL2.dll");
        if (!sdl) return;
        GetWindowFn focus = (GetWindowFn)GetProcAddress(sdl, "SDL_GetKeyboardFocus");
        GetWindowFn current = (GetWindowFn)GetProcAddress(sdl, "SDL_GL_GetCurrentWindow");
        GetFlagsFn flags = (GetFlagsFn)GetProcAddress(sdl, "SDL_GetWindowFlags");
        setFullscreen = (SetFullscreenFn)GetProcAddress(sdl, "SDL_SetWindowFullscreen");
        if (!flags || !setFullscreen) return;
        void *w = focus ? focus() : 0;
        if (!w && current) w = current();
        if (!w) return;
        const unsigned SDL_WINDOW_FULLSCREEN_DESKTOP = 0x1001, SDL_WINDOW_FULLSCREEN = 0x1;
        unsigned f = flags(w);
        if (f & SDL_WINDOW_FULLSCREEN) {
            mode = f & SDL_WINDOW_FULLSCREEN_DESKTOP;
            if (setFullscreen(w, 0) == 0) window = w;
        }
    }
    ~LeaveFullscreen() {
        if (window) setFullscreen(window, mode);
    }
};

enum { ID_TC_STATUS = 560, ID_TC_PAUSE, ID_TC_RESUME, ID_TC_SLOW, ID_TC_NORMAL, ID_TC_FAST, ID_TC_X5,
       ID_TC_X10, ID_TC_WARP };

static const int kWarpTicks = 3 * B200TC_TICKS_PER_YEAR;  // "+3 years"

// A tiny wide-string builder: no C runtime formatting in the dialog code.
static wchar_t *PutText(wchar_t *p, const wchar_t *s) {
    while (*s) *p++ = *s++;
    return p;
}

static void RefreshTime(HWND dlg) {
    int speed = UnderlyingSpeed();
    const wchar_t *name = speed == (int)B200TC_SPEED_SLOW ? L"slow" : speed == (int)B200TC_SPEED_NORMAL ? L"normal"
                        : speed == (int)B200TC_SPEED_FAST ? L"fast" : speed == (int)B200TC_SPEED_5X ? L"5x"
                        : speed == (int)B200TC_SPEED_10X ? L"10x" : L"custom";
    wchar_t s[128];
    wchar_t *p = PutText(s, GamePaused() ? L"Paused" : L"Running");
    p = PutText(p, L". Speed: ");
    p = PutText(p, name);
    p = PutText(p, L".");
    if (WarpUnderWay()) p = PutText(p, L" A time warp is under way.");
    *p = 0;
    SetDlgItemTextW(dlg, ID_TC_STATUS, s);
}

static INT_PTR CALLBACK TimeProc(HWND dlg, UINT msg, WPARAM wp, LPARAM) {
    switch (msg) {
    case WM_INITDIALOG: RefreshTime(dlg); return TRUE;
    case WM_COMMAND:
        switch (LOWORD(wp)) {
        case ID_TC_PAUSE: PauseGame(); break;
        case ID_TC_RESUME: ResumeGame(); break;
        case ID_TC_SLOW: ChooseSpeed(B200TC_SPEED_SLOW); break;
        case ID_TC_NORMAL: ChooseSpeed(B200TC_SPEED_NORMAL); break;
        case ID_TC_FAST: ChooseSpeed(B200TC_SPEED_FAST); break;
        case ID_TC_X5: ChooseSpeed(B200TC_SPEED_5X); break;
        case ID_TC_X10: ChooseSpeed(B200TC_SPEED_10X); break;
        case ID_TC_WARP:
            if (MessageBoxW(dlg, L"Everyone at home ages at once, with every normal rule: birthdays, leaving "
                                 L"home, and old age. Continue?", L"Time Warp",
                            MB_YESNO | MB_ICONQUESTION) == IDYES)
                StartTimeWarp(kWarpTicks);
            break;
        case IDOK: case IDCANCEL: EndDialog(dlg, 0); return TRUE;
        }
        RefreshTime(dlg);
        return TRUE;
    case WM_CLOSE: EndDialog(dlg, 0); return TRUE;
    }
    return FALSE;
}

static Template TimeTemplate;  // file scope: no run-time initialiser, no C runtime guard

static void ShowTimeControls(HWND owner) {
    Template &t = TimeTemplate;
    t.Begin(L"Time Controls", 250, 150, 10);
    t.Item(STATIC, SS_LEFT, 10, 8, 230, 12, ID_TC_STATUS, L"");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 10, 24, 112, 16, ID_TC_PAUSE, L"Pause");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 128, 24, 112, 16, ID_TC_RESUME, L"Resume");
    // Virtual Villagers' three speeds, then the two faster extras.
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 10, 48, 73, 16, ID_TC_SLOW, L"Slow");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 88, 48, 74, 16, ID_TC_NORMAL, L"Normal");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 167, 48, 73, 16, ID_TC_FAST, L"Fast");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 10, 68, 112, 16, ID_TC_X5, L"5x");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 128, 68, 112, 16, ID_TC_X10, L"10x");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 10, 94, 230, 16, ID_TC_WARP, L"Time Warp: +3 years");
    t.Item(BUTTON, BS_DEFPUSHBUTTON | WS_TABSTOP, 165, 126, 75, 16, IDOK, L"Close");
    DialogBoxIndirectParamW(ThisModule, t.Get(), owner, TimeProc, 0);
}

// ---------------------------------------------------------------- Settings hooks
// Add the button: the constructor's own sequence for its Evict button (new,
// GetImageGrid, ldwButton, SetText with the dialog's colour and Evict's font,
// AddControl). Its x is 30 (the mirror of Evict's 466 about Done); its y is
// Evict's: the dialog's height - Done's height - 1Eh, from Done's own height
// virtual as the constructor reads it.
static void __cdecl AddTimeButton(unsigned char *dialog) {
    void *done = *(void **)(dialog + B200TC_OPTIONS_DONE_BUTTON_FIELD);
    if (!done) return;
    void **vtable = *(void ***)done;
    int height = ((ControlSizeFn)vtable[B200TC_CONTROL_HEIGHT_VOFFSET / 4])(done);
    int top = *(int *)(dialog + B200TC_SCENE_TOP_FIELD);
    int bottom = *(int *)(dialog + B200TC_SCENE_BOTTOM_FIELD);
    ldwPoint pos = { (int)B200TC_OPTIONS_TIME_X,
                     (bottom - top) - height - (int)B200TC_OPTIONS_BUTTON_BOTTOM_MARGIN };
    void *memory = GameNew(0x14);
    if (!memory) return;
    void *grid = GetImageGrid(GraphicsGet(), B200TC_OPTIONS_BUTTON_IMAGE);
    void *button = ButtonCtor(memory, kTimeButtonId, grid, pos, dialog, false);
    unsigned colour = *(unsigned *)SITE(OPTIONS_TEXT_COLOUR);
    void *font = GetEvictFont(*(void **)(dialog + B200TC_OPTIONS_STRING_MANAGER_FIELD));
    ButtonSetText(button, kTimeButtonText, colour, colour, colour, font);
    AddControl(dialog, button);
}

// The constructor's last call, `call SetChecked` (ecx = the last check box,
// one bool argument, ret 4), lands here with ebx = the dialog. The same call,
// then the button. eax, ecx and edx are dead when the constructor resumes;
// AddTimeButton (cdecl) keeps ebx, esi, edi and ebp.
static __declspec(naked) void OptionsCtorLastCall() {
    __asm {
        push dword ptr [esp + 4]
        call dword ptr [NativeSetChecked]
        push ebx
        call AddTimeButton
        add esp, 4
        ret 4
    }
}

static bool __fastcall OptionsHandleMessage(void *dialog, void *, int message, long param) {
    if (message == B200TC_MESSAGE_BUTTON_CLICKED && param == kTimeButtonId) {
        LeaveFullscreen windowed;
        ShowTimeControls(GetActiveWindow());
        return true;
    }
    return NativeOptionsHandleMessage(dialog, message, param);
}

static void PlanTimeControls(Plan &plan) {
    plan.Retarget(SITE(OPTIONS_CTOR_LAST_CALL), (const void *)&OptionsCtorLastCall);
    plan.Slot(SITE(OPTIONS_SLOT_HANDLE_MESSAGE), (const void *)&OptionsHandleMessage);
    plan.Retarget(SITE(TIMEFLOW_INCREMENT_AGE_CALL), (const void *)&IncrementAgeWithWarp);
    plan.Slot(SITE(GAME_STATE_SLOT_SAVE), (const void *)&GameStateSaveSlot);
    plan.Slot(SITE(GAME_STATE_SLOT_LOAD), (const void *)&GameStateLoadSlot);
}
