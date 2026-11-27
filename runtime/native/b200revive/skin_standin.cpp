// A stand-in for the Skin Tones DLL (vf2skin_b200.dll) in the Revive harness only (tests/test_b200_revive.py): it
// answers B200Skin_ToneOf(slot) with tone 3 + slot and birth tone 7 (or -1 for slot 1, "no tone") and records the
// last B200Skin_ToneGive. Never shipped.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

extern "C" __declspec(dllexport) volatile int B200SkinStandin_Given[4] = { 0, -1, -1, -1 };   // count, slot, tone, birth

extern "C" __declspec(dllexport) int __cdecl B200Skin_ToneOf(int slot) {
    return slot == 1 ? -1 : (3 + slot) | (7 << 8);
}

extern "C" __declspec(dllexport) void __cdecl B200Skin_ToneGive(int slot, int tone, int birthTone) {
    B200SkinStandin_Given[0] += 1;
    B200SkinStandin_Given[1] = slot;
    B200SkinStandin_Given[2] = tone;
    B200SkinStandin_Given[3] = birthTone;
}

BOOL WINAPI DllMain(HINSTANCE, DWORD, LPVOID) { return TRUE; }
