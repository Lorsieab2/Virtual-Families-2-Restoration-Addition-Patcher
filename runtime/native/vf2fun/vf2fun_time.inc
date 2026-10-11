// vf2fun_time.inc -- module time_controls; included by vf2fun.cpp after the
// host registry and the shared game ABI.
//
// NEW in the runtime build (B200 has no equivalent): the Virtual Families 1
// patcher's "Time Controls" Windows dialog. Pause, Resume, Normal / 2x / 5x /
// 10x speed and one "Time Warp: +3 years". Opened by a button added to the
// store screen (CScrollingStoreScene), the way the Virtual Families 1 patcher
// adds its Upgrades button next to Done.
//
//   1. The store constructor's last call (`push 2; call SetStoreCategory`) is
//      retargeted to a wrapper that makes the same call and then adds one more
//      button of the store's own art, in the next slot to the right of Back.
//   2. CScrollingStoreScene::HandleMessage's entry is detoured (the stolen
//      prologue runs through a trampoline). A click on that button opens the
//      dialog; every other message goes to the game's own handler unchanged.
//   3. Speed and pause use the game's own CGameTime::SetSpeed and the speed
//      field in theGameState, exactly as the Space key does. Nothing here
//      stores a speed of its own, so the game's own save keeps it.
//   4. Time Warp queues extra age ticks that the game's own
//      AllVillagersTimeflowUpkeep feeds through CVillagerBio::IncrementAge
//      (5 bytes there are replaced by a jump to WarpStub). No age is written
//      directly, so leaving home at 19 and the oldest-age record still run.
//
// With the TimeControls key off none of this is installed: the game is stock.

static bool TimeControls;

// ---------------------------------------------------------------- game ABI
struct ldwPoint { int x, y; };

typedef void (__thiscall *SetSpeedFn)(void *time, int speed);
typedef void *(__cdecl *NewFn)(size_t size);
typedef void *(__cdecl *GetManagerFn)();
typedef void *(__thiscall *GetImageGridFn)(void *graphics, int image);
typedef void *(__thiscall *GetLargeFontFn)(void *strings);
typedef void *(__thiscall *ButtonCtorFn)(void *self, int id, void *grid, ldwPoint pos, void *scene, bool flag);
typedef void (__thiscall *ButtonSetTextFn)(void *self, const char *text, unsigned c1, unsigned c2,
                                           unsigned c3, void *font);
typedef void (__thiscall *AddControlFn)(void *scene, void *control);
typedef void (__thiscall *SetStoreCategoryFn)(void *scene, int category);
typedef bool (__thiscall *StoreHandleMessageFn)(void *scene, int message, long param);

static const SetSpeedFn SetSpeed = (SetSpeedFn)VF2_SET_SPEED;
static void *const GameTime = (void *)VF2_GAME_TIME;
static const NewFn GameNew = (NewFn)VF2_GAME_NEW;
static const GetManagerFn GraphicsGet = (GetManagerFn)VF2_GRAPHICS_GET;
static const GetImageGridFn GetImageGrid = (GetImageGridFn)VF2_GRAPHICS_GET_IMAGE_GRID;
static const GetManagerFn StringsGet = (GetManagerFn)VF2_STRING_GET;
static const GetLargeFontFn GetLargeFont = (GetLargeFontFn)VF2_STRING_GET_LARGE_FONT;
static const ButtonCtorFn ButtonCtor = (ButtonCtorFn)VF2_BUTTON_CTOR;
static const ButtonSetTextFn ButtonSetText = (ButtonSetTextFn)VF2_BUTTON_SET_TEXT;
static const AddControlFn AddControl = (AddControlFn)VF2_SCENE_ADD_CONTROL;
static const SetStoreCategoryFn NativeSetStoreCategory = (SetStoreCategoryFn)VF2_STORE_SET_CATEGORY;
static StoreHandleMessageFn OriginalStoreHandleMessage;  // the trampoline

static const int kTimeButtonId = 0x5646;  // 'VF': the store knows only ids 1, 2 and 3
static const char kTimeButtonText[] = "Time";

// ---------------------------------------------------------------- pause and speed
// theGameState keeps the speed in one int (+0x25B18). 10 is normal, 5 is 2x,
// 2 is 5x, 1 is 10x. The Space key pauses by SetSpeed(999) and adding 999 to
// the field, and resumes by SetSpeed(field - 999) and storing that, so the
// speed to come back to rides along as the part below 999. These do the same.
static int *SpeedField() {
    unsigned char *state = *(unsigned char **)VF2_GAME_STATE_INSTANCE_PTR;
    return state ? (int *)(state + VF2_GAME_STATE_SPEED_FIELD) : 0;
}

static bool GamePaused() {
    int *field = SpeedField();
    return field && *field >= VF2_PAUSED_OFFSET;
}

// The speed the game runs at when not paused.
static int UnderlyingSpeed() {
    int *field = SpeedField();
    if (!field) return VF2_SPEED_NORMAL;
    int speed = *field >= VF2_PAUSED_OFFSET ? *field - VF2_PAUSED_OFFSET : *field;
    return speed > 0 ? speed : VF2_SPEED_NORMAL;
}

static void PauseGame() {
    int *field = SpeedField();
    if (!field || *field >= VF2_PAUSED_OFFSET) return;
    SetSpeed(GameTime, VF2_PAUSED_OFFSET);
    *field += VF2_PAUSED_OFFSET;
}

// Stock Space does SetSpeed(0) when the field is exactly 999; the speed is
// normal then, as in the Options dialog.
static void ResumeGame() {
    int *field = SpeedField();
    if (!field || *field < VF2_PAUSED_OFFSET) return;
    int speed = *field - VF2_PAUSED_OFFSET;
    if (speed <= 0) speed = VF2_SPEED_NORMAL;
    SetSpeed(GameTime, speed);
    *field = speed;
}

static void ChooseSpeed(int speed) {
    int *field = SpeedField();
    if (!field) return;
    if (*field >= VF2_PAUSED_OFFSET) {
        *field = VF2_PAUSED_OFFSET + speed;  // stays paused; Resume restores this speed
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
    return v && v[VF2_VILLAGER_ACTIVE_OFFSET] && !v[VF2_VILLAGER_LEFT_HOME_OFFSET] &&
           *(const int *)(v + VF2_VILLAGER_HEALTH_OFFSET) > 0;
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

// Called by WarpStub for every villager the game ages: `leftHomeByte` is the
// loop pointer (villager + 0x1BB88) and `ticks` the native ticks.
static int __cdecl WarpTicksFor(const unsigned char *leftHomeByte, int ticks) {
    if (!WarpTicks) return ticks;
    unsigned offset = (unsigned)(leftHomeByte - VF2_VILLAGER_LEFT_HOME_OFFSET) -
                      (VF2_VILLAGER_MANAGER + VF2_VILLAGER_ARRAY_OFFSET);
    if (offset % VF2_VILLAGER_STRIDE != 0 || offset / VF2_VILLAGER_STRIDE >= 30) return ticks;
    unsigned bit = 1u << (offset / VF2_VILLAGER_STRIDE);
    if (!(WarpPending & bit)) return ticks;
    WarpPending &= ~bit;
    int warp = WarpTicks;
    if (!WarpPending) WarpTicks = 0;
    VF2_COUNT(timeWarpsApplied);
    return ticks + warp;
}

// Replaces `mov ecx,edi; mov ebx,eax; push ebx` (5 bytes) before the
// `call IncrementAge` at 0x499898. eax = the native ticks, edi = &age,
// esi = &leftHome byte. ebx keeps the NATIVE ticks: the accumulator
// remainder after the call is computed from them.
static unsigned WarpResume = VF2_WARP_RESUME;

static __declspec(naked) void WarpStub() {
    __asm {
        mov ebx, eax
        push ebx
        push esi
        call WarpTicksFor
        add esp, 8
        mov ecx, edi
        push eax
        jmp dword ptr [WarpResume]
    }
}

// ---------------------------------------------------------------- the dialog
// Built in memory (no resource script), like the Virtual Families 1 patcher's.
class Template {
    WORD buf[4096];
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

enum { ID_TC_STATUS = 560, ID_TC_PAUSE, ID_TC_RESUME, ID_TC_NORMAL, ID_TC_X2, ID_TC_X5, ID_TC_X10,
       ID_TC_WARP };

static const int kWarpTicks = 3 * VF2_TICKS_PER_YEAR;  // "+3 years"

static void RefreshTime(HWND dlg) {
    int speed = UnderlyingSpeed();
    const wchar_t *name = speed == 5 ? L"2x" : speed == 2 ? L"5x" : speed == 1 ? L"10x"
                        : speed == VF2_SPEED_NORMAL ? L"normal" : L"custom";
    wchar_t s[128];
    _snwprintf_s(s, 128, _TRUNCATE, L"%s. Speed: %s.%s", GamePaused() ? L"Paused" : L"Running", name,
                 WarpUnderWay() ? L" A time warp is under way." : L"");
    SetDlgItemTextW(dlg, ID_TC_STATUS, s);
}

static INT_PTR CALLBACK TimeProc(HWND dlg, UINT msg, WPARAM wp, LPARAM) {
    switch (msg) {
    case WM_INITDIALOG: RefreshTime(dlg); return TRUE;
    case WM_COMMAND:
        switch (LOWORD(wp)) {
        case ID_TC_PAUSE: PauseGame(); break;
        case ID_TC_RESUME: ResumeGame(); break;
        case ID_TC_NORMAL: ChooseSpeed(VF2_SPEED_NORMAL); break;
        case ID_TC_X2: ChooseSpeed(5); break;
        case ID_TC_X5: ChooseSpeed(2); break;
        case ID_TC_X10: ChooseSpeed(1); break;
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

static void ShowTimeControls(HWND owner) {
    static Template t;
    t.Begin(L"Time Controls", 250, 150, 9);
    t.Item(STATIC, SS_LEFT, 10, 8, 230, 12, ID_TC_STATUS, L"");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 10, 24, 112, 16, ID_TC_PAUSE, L"Pause");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 128, 24, 112, 16, ID_TC_RESUME, L"Resume");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 10, 48, 53, 16, ID_TC_NORMAL, L"Normal");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 69, 48, 53, 16, ID_TC_X2, L"2x");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 128, 48, 53, 16, ID_TC_X5, L"5x");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 187, 48, 53, 16, ID_TC_X10, L"10x");
    t.Item(BUTTON, BS_PUSHBUTTON | WS_TABSTOP, 10, 76, 230, 16, ID_TC_WARP, L"Time Warp: +3 years");
    t.Item(BUTTON, BS_DEFPUSHBUTTON | WS_TABSTOP, 165, 126, 75, 16, IDOK, L"Close");
    DialogBoxIndirectParamW(Module, t.Get(), owner, TimeProc, 0);
}

// ---------------------------------------------------------------- store hooks
// Add the button: the game's own sequence for its Done / Back buttons.
static void AddTimeButton(void *scene) {
    void *memory = GameNew(0x14);
    if (!memory) return;
    void *grid = GetImageGrid(GraphicsGet(), VF2_BUTTON_IMAGE);
    int widescreen = *(int *)((unsigned char *)scene + VF2_STORE_WIDESCREEN_OFFSET_FIELD);
    ldwPoint pos = { widescreen + (int)VF2_STORE_TIME_BUTTON_X, (int)VF2_STORE_TIME_BUTTON_Y };
    void *button = ButtonCtor(memory, kTimeButtonId, grid, pos, scene, false);
    unsigned colour = *(unsigned *)VF2_BUTTON_TEXT_COLOUR;
    ButtonSetText(button, kTimeButtonText, colour, colour, colour, GetLargeFont(StringsGet()));
    AddControl(scene, button);
    VF2_COUNT(timeButtonsAdded);
}

// The constructor's `push 2; call SetStoreCategory` lands here (ecx = scene).
static void __fastcall StoreCtorSetCategory(void *scene, void *, int category) {
    NativeSetStoreCategory(scene, category);
    AddTimeButton(scene);
}

static bool __fastcall StoreHandleMessageDetour(void *scene, void *, int message, long param) {
    if (message == VF2_MESSAGE_BUTTON_CLICKED && param == kTimeButtonId) {
        VF2_COUNT(timeDialogOpens);
        LeaveFullscreen windowed;
        ShowTimeControls(GetActiveWindow());
        return true;
    }
    return OriginalStoreHandleMessage(scene, message, param);
}

static void PlanTimeControls(Plan &plan) {
    OriginalStoreHandleMessage = (StoreHandleMessageFn)plan.Trampoline(
        VF2_STORE_HANDLE_MESSAGE, VF2_STORE_HANDLE_MESSAGE_STEAL);
    plan.Jmp(VF2_STORE_HANDLE_MESSAGE, VF2_STORE_HANDLE_MESSAGE_STEAL, (const void *)&StoreHandleMessageDetour);
    plan.Retarget(VF2_STORE_CTOR_SET_CATEGORY_CALL, (const void *)&StoreCtorSetCategory);
    plan.Jmp(VF2_WARP_SITE, VF2_WARP_SITE_LEN, (const void *)&WarpStub);
    if (!OriginalStoreHandleMessage) plan.ok = false;
}

// ---------------------------------------------------------------- test builds only
#ifdef VF2FUN_TEST_COUNTERS
// Lets the harness drive the pause, speed and warp state machine and the
// dialog without a game window. op: 1 pause, 2 resume, 3 speed(arg),
// 4 start a warp of arg ticks, 5 warp pending villager count, 6 speed field.
extern "C" __declspec(dllexport) int __cdecl VF2Fun_TestTime(int op, int arg) {
    switch (op) {
    case 1: PauseGame(); return 0;
    case 2: ResumeGame(); return 0;
    case 3: ChooseSpeed(arg); return 0;
    case 4: StartTimeWarp(arg); return 0;
    case 5: {
        WarpUnderWay();
        int n = 0;
        for (unsigned bits = WarpPending; bits; bits &= bits - 1) ++n;
        return n;
    }
    case 6: return SpeedField() ? *SpeedField() : -1;
    }
    return -1;
}
extern "C" __declspec(dllexport) void __cdecl VF2Fun_TestShowTime(HWND owner) {
    ShowTimeControls(owner);
}
#endif
