#include <windows.h>

static FARPROC vf2_fmod_proc(const char *name)
{
    static HMODULE module = NULL;
    if (!module) {
        module = LoadLibraryA("fmod.dll");
    }
    return module ? GetProcAddress(module, name) : NULL;
}

#define FMOD_STDCALL(ret, name, decorated, args, params, fail) \
extern "C" ret __stdcall name args \
{ \
    typedef ret (__stdcall *Fn) args; \
    Fn fn = reinterpret_cast<Fn>(vf2_fmod_proc(decorated)); \
    if (!fn) return fail; \
    return fn params; \
}

FMOD_STDCALL(signed char, FMUSIC_FreeSong, "_FMUSIC_FreeSong@4", (void *a), (a), 0)
FMOD_STDCALL(signed char, FMUSIC_PlaySong, "_FMUSIC_PlaySong@4", (void *a), (a), 0)
FMOD_STDCALL(signed char, FMUSIC_StopSong, "_FMUSIC_StopSong@4", (void *a), (a), 0)
FMOD_STDCALL(signed char, FMUSIC_StopAllSongs, "_FMUSIC_StopAllSongs@0", (void), (), 0)
FMOD_STDCALL(signed char, FMUSIC_SetLooping, "_FMUSIC_SetLooping@8", (void *a, signed char b), (a, b), 0)
FMOD_STDCALL(signed char, FMUSIC_SetMasterVolume, "_FMUSIC_SetMasterVolume@8", (void *a, int b), (a, b), 0)
FMOD_STDCALL(signed char, FMUSIC_IsPlaying, "_FMUSIC_IsPlaying@4", (void *a), (a), 0)
FMOD_STDCALL(unsigned int, FMUSIC_GetTime, "_FMUSIC_GetTime@4", (void *a), (a), 0)
FMOD_STDCALL(void *, FMUSIC_LoadSong, "_FMUSIC_LoadSong@4", (const char *a), (a), NULL)

FMOD_STDCALL(signed char, FSOUND_Init, "_FSOUND_Init@12", (int a, int b, unsigned int c), (a, b, c), 0)
FMOD_STDCALL(void, FSOUND_Close, "_FSOUND_Close@0", (void), (), )
FMOD_STDCALL(signed char, FSOUND_SetSFXMasterVolume, "_FSOUND_SetSFXMasterVolume@4", (int a), (a), 0)
FMOD_STDCALL(void *, FSOUND_Sample_Load, "_FSOUND_Sample_Load@20", (int a, const char *b, unsigned int c, int d, int e), (a, b, c, d, e), NULL)
FMOD_STDCALL(signed char, FSOUND_Sample_Free, "_FSOUND_Sample_Free@4", (void *a), (a), 0)
FMOD_STDCALL(signed char, FSOUND_Sample_SetMode, "_FSOUND_Sample_SetMode@8", (void *a, unsigned int b), (a, b), 0)
FMOD_STDCALL(int, FSOUND_PlaySound, "_FSOUND_PlaySound@8", (int a, void *b), (a, b), -1)
FMOD_STDCALL(signed char, FSOUND_StopSound, "_FSOUND_StopSound@4", (int a), (a), 0)
FMOD_STDCALL(signed char, FSOUND_SetVolume, "_FSOUND_SetVolume@8", (int a, int b), (a, b), 0)
FMOD_STDCALL(signed char, FSOUND_IsPlaying, "_FSOUND_IsPlaying@4", (int a), (a), 0)
FMOD_STDCALL(void *, FSOUND_Stream_Open, "_FSOUND_Stream_Open@16", (const char *a, unsigned int b, int c, int d), (a, b, c, d), NULL)
FMOD_STDCALL(signed char, FSOUND_Stream_Close, "_FSOUND_Stream_Close@4", (void *a), (a), 0)
FMOD_STDCALL(int, FSOUND_Stream_Play, "_FSOUND_Stream_Play@8", (int a, void *b), (a, b), -1)
FMOD_STDCALL(signed char, FSOUND_Stream_Stop, "_FSOUND_Stream_Stop@4", (void *a), (a), 0)
FMOD_STDCALL(unsigned int, FSOUND_Stream_GetTime, "_FSOUND_Stream_GetTime@4", (void *a), (a), 0)
FMOD_STDCALL(signed char, FSOUND_Stream_SetMode, "_FSOUND_Stream_SetMode@8", (void *a, unsigned int b), (a, b), 0)
