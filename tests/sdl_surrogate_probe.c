/* What the game's own SDL2.dll (2.0.3) gives for characters typed the way Windows and input methods send them:
   SendInput with KEYEVENTF_UNICODE, one key down/up per UTF-16 unit (two for a character beyond U+FFFF).
   A small SDL window of this probe is made the foreground window, and every SendInput is made only while it still
   is (nothing can reach another program). Prints each SDL_TEXTINPUT's bytes. Usage: sdlprobe2 <SDL2.dll> */
#include <windows.h>
#include <stdio.h>

typedef int (__cdecl *InitFn)(unsigned);
typedef void *(__cdecl *CreateFn)(const char *, int, int, int, int, unsigned);
typedef int (__cdecl *PollFn)(void *);
typedef void (__cdecl *StartFn)(void);
typedef int (__cdecl *WmFn)(void *, void *);
typedef void (__cdecl *DelayFn)(unsigned);

static int send_unit(HWND hwnd, WORD unit) {
    if (GetForegroundWindow() != hwnd) return 0;
    INPUT in[2];
    ZeroMemory(in, sizeof(in));
    in[0].type = INPUT_KEYBOARD; in[0].ki.wScan = unit; in[0].ki.dwFlags = KEYEVENTF_UNICODE;
    in[1] = in[0]; in[1].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;
    return SendInput(2, in, sizeof(INPUT)) == 2;
}

int main(int argc, char **argv) {
    HMODULE sdl = LoadLibraryA(argv[1]);
    if (!sdl) { printf("no SDL\n"); return 1; }
    InitFn init = (InitFn)GetProcAddress(sdl, "SDL_Init");
    CreateFn create = (CreateFn)GetProcAddress(sdl, "SDL_CreateWindow");
    PollFn poll = (PollFn)GetProcAddress(sdl, "SDL_PollEvent");
    StartFn start = (StartFn)GetProcAddress(sdl, "SDL_StartTextInput");
    WmFn wm = (WmFn)GetProcAddress(sdl, "SDL_GetWindowWMInfo");
    DelayFn delay = (DelayFn)GetProcAddress(sdl, "SDL_Delay");
    if (init(0x20) != 0) { printf("init failed\n"); return 1; }
    void *win = create("probe", 40, 40, 96, 64, 0x4);
    start();
    unsigned char info[64] = {0};
    info[0] = 2; info[1] = 0; info[2] = 3;
    if (!wm(win, info)) { printf("no wm info\n"); return 1; }
    HWND hwnd = *(HWND *)(info + 8);
    unsigned char ev[56];
    for (int k = 0; k < 50 && GetForegroundWindow() != hwnd; ++k) {
        SetForegroundWindow(hwnd);
        while (poll(ev)) {}
        delay(20);
    }
    if (GetForegroundWindow() != hwnd) { printf("could not become the foreground window: nothing sent\n"); return 2; }
    const WORD cases[][2] = { {0x00E9, 0}, {0x65E5, 0}, {0xD83D, 0xDC4D}, {0xD808, 0xDC00} };
    for (int c = 0; c < 4; ++c) {
        while (poll(ev)) {}
        int ok = send_unit(hwnd, cases[c][0]);
        if (ok && cases[c][1]) ok = send_unit(hwnd, cases[c][1]);
        if (!ok) { printf("lost the foreground: stopped\n"); return 2; }
        printf("case %04X %04X:", cases[c][0], cases[c][1]);
        for (int k = 0; k < 10; ++k) {
            while (poll(ev)) {
                if (*(unsigned *)ev == 0x303) {
                    printf(" [");
                    for (int i = 0; ev[12 + i] && i < 32; ++i) printf("%02X", ev[12 + i]);
                    printf("]");
                }
            }
            delay(10);
        }
        printf("\n");
    }
    return 0;
}
