// A stand-in for the Family History DLL (vf2history_b200.dll) in the Revive harness only (tests/test_b200_revive.py):
// B200History_LogName answers "Bob" with a whole name longer than the save's field (in UTF-8) and any other name
// with itself; B200History_Revived records the slot it was given. Never shipped.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

extern "C" __declspec(dllexport) volatile int B200HistoryStandin_Revived[2] = { 0, -1 };   // count, last slot

extern "C" __declspec(dllexport) void __cdecl B200History_Revived(int slot) {
    B200HistoryStandin_Revived[0] += 1;
    B200HistoryStandin_Revived[1] = slot;
}

extern "C" __declspec(dllexport) int __cdecl B200History_LogName(const char *stored, char *out, int cap) {
    static const char bob[] = "Bob Bartholomew \xC3\x89lodie-Whole-Name-Longer-Than-The-Field";
    const char *name = (stored[0] == 'B' && stored[1] == 'o' && stored[2] == 'b' && !stored[3]) ? bob : stored;
    int n = 0;
    while (name[n] && n + 1 < cap) { out[n] = name[n]; ++n; }
    out[n] = 0;
    return n;
}

BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) { return TRUE; }
