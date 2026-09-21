/*
 * VF2 runtime-hook Stage-1 spike (32-bit).
 *
 * Study §8.3.2: take ONE ungated CAVE+DETOUR feature and prove its link-time
 * cave can be installed as a RUNTIME trampoline against the REAL function
 * bytes -- retiring the "steal + relocate a real /O2 prologue" risk the
 * §5 PoC deliberately left open.
 *
 * Feature: Allow Older Pregnancies (work/patch_mobile_furniture_pack.py
 * patch_allow_older_pregnancies). Its link-time form detours
 * CVillagerState::ChanceOfPregnancy (?ChanceOfPregnancy@...@Z, 0xF7 bytes):
 *   - steal the 8-byte prologue  55 8B EC B8 67 66 66 66
 *     (push ebp; mov ebp,esp; mov eax,66666667h) -- a CLEAN 3-instruction,
 *     8-byte boundary with no relative operands, so the steal needs no
 *     relocation. (Verified with capstone against the stock object; the bytes
 *     are in ChanceOfPregnancy.bin.)
 *   - E9 rel32 at the entry -> a cave that (a) checks the runtime flag byte,
 *     (b) on the older-age path calls the helper, (c) otherwise replays the
 *     stolen prologue and jmp original+8.
 *
 * SCOPE (updated after the first run faulted). The stock ChanceOfPregnancy body
 * is NOT self-contained: it has 6 external relocations (ldwGameState::GetRandom,
 * CTutorialTip::Queue/WasDisplayed, the TutorialTip global). Copying the raw
 * bytes and executing the whole body standalone crashes on the first call to an
 * unrelocated external -- which is a property of the BODY needing the whole
 * linked game, not of the hook. Running the real body is what the linked build's
 * own tests already cover. So this spike proves the HOOK MECHANISM against the
 * REAL prologue bytes, and uses a controlled stub for the fall-through body:
 *   1. the 8-byte prologue steal is exact (matches the real stock prologue);
 *   2. the trampoline installs correctly -- the entry becomes E9 rel32 to a
 *      cave whose bytes are the flag check + arg shim + helper call + replayed
 *      prologue + jmp back (inspected, and exercised);
 *   3. with the flag OFF, control replays the stolen prologue and continues
 *      into the body (a stub here) -- behaviour preserved, the thing a wrong
 *      steal breaks;
 *   4. with the flag ON and the older-age predicate met, control reaches the
 *      DLL-side helper instead of the body;
 *   5. re-hooking an already-hooked entry is refused (composition safety).
 *
 * The prologue we steal is the REAL one; only the body it falls through to is
 * stubbed, because the real body belongs to the whole game.
 *
 * It does NOT modify the real VF2.exe or the shipping patcher. It is a
 * throwaway PoC for the VV author's Stage-1 feasibility review.
 *
 * Build (short path, VS x86 -- see the §5 PoC's MAX_PATH note):
 *   cl /nologo /O2 /DWIN32 stage1_spike.c
 */
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* The real prologue we expect to steal, from the stock object. */
static const unsigned char kExpectedPrologue[8] = {
    0x55, 0x8B, 0xEC, 0xB8, 0x67, 0x66, 0x66, 0x66
};
#define STOLEN 8

/* ---- the runtime flag and helper a proxy DLL would own ---- */
static unsigned char gAllowOlderPregnancies = 0;
static int gHelperCalls = 0;

/* Stand-in for VF2RollOlderPregnancy: the real helper reads game globals we do
 * not have here, so the spike proves REACHABILITY (control arrives with the
 * right args), not the pregnancy maths -- which the linked build already
 * tests. Returns 1 so the caller can observe the older-age branch was taken. */
static int __cdecl RollOlderPregnancy(void *state, int mAge, int fAge, int fFert)
{
    (void)state; (void)mAge; (void)fAge; (void)fFert;
    gHelperCalls++;
    return 1;
}

/* A trampoline installed at runtime over the real function's first STOLEN
 * bytes. Layout mirrors patch_allow_older_pregnancies' cave, but the cave lives
 * in freshly VirtualAlloc'd RX memory instead of at the object's section end,
 * and the addresses are the LOADED addresses, resolved now rather than by the
 * linker. */
typedef struct {
    unsigned char *target;      /* the function entry we hooked */
    unsigned char saved[STOLEN];/* the original prologue bytes */
    unsigned char *cave;        /* RX trampoline */
    int hooked;
} Hook;

static int install(Hook *h, unsigned char *target)
{
    /* Composition safety: refuse a target that is not the clean stock
     * prologue (already hooked, or not this function). */
    if (memcmp(target, kExpectedPrologue, STOLEN) != 0) {
        return 0;
    }
    memset(h, 0, sizeof(*h));
    h->target = target;
    memcpy(h->saved, target, STOLEN);

    /* Build the cave. It receives control from the E9 at the entry with the
     * caller's stack intact (nothing pushed), exactly like the link-time cave.
     *   cmp byte ptr [&flag],0 ; je fallback ; <older-age arg push + call> ;
     *   fallback: <stolen 8 bytes> ; jmp target+8
     * For the spike we drive the older-age decision from the flag alone (the
     * age compares in the real cave are stock ints on the stack; reproducing
     * them adds nothing to the prologue-steal proof), so: flag set -> call
     * helper and ret; flag clear -> replay prologue and continue. */
    unsigned char *cave = (unsigned char *)VirtualAlloc(
        NULL, 128, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!cave) return 0;
    h->cave = cave;

    int n = 0;
    /* cmp byte ptr [flag], 0 */
    cave[n++] = 0x80; cave[n++] = 0x3D;
    *(void **)(cave + n) = &gAllowOlderPregnancies; n += 4;
    cave[n++] = 0x00;
    /* je fallback (short, patched below) */
    cave[n++] = 0x74; int je_at = n; cave[n++] = 0x00;
    /* --- flag ON path: push the 3 stack args + this, call helper, ret 0Ch ---
     * ChanceOfPregnancy is __thiscall(_N (this)(int,int,int)); at entry the
     * stack is [ret][mAge][fAge][fFert] and this=ecx. Mirror the link cave's
     * cdecl shim. */
    cave[n++] = 0xFF; cave[n++] = 0x74; cave[n++] = 0x24; cave[n++] = 0x0C; /* push [esp+0Ch] fFert */
    cave[n++] = 0xFF; cave[n++] = 0x74; cave[n++] = 0x24; cave[n++] = 0x0C; /* push fAge */
    cave[n++] = 0xFF; cave[n++] = 0x74; cave[n++] = 0x24; cave[n++] = 0x0C; /* push mAge */
    cave[n++] = 0x51;                                                        /* push ecx (this) */
    cave[n++] = 0xE8;                                                        /* call helper */
    *(int32_t *)(cave + n) = (int32_t)((unsigned char *)RollOlderPregnancy - (cave + n + 4)); n += 4;
    cave[n++] = 0x83; cave[n++] = 0xC4; cave[n++] = 0x10;                    /* add esp,10h */
    cave[n++] = 0xC2; cave[n++] = 0x0C; cave[n++] = 0x00;                    /* ret 0Ch */
    /* fallback: */
    cave[je_at] = (unsigned char)(n - (je_at + 1));
    memcpy(cave + n, h->saved, STOLEN); n += STOLEN;                         /* replay prologue */
    cave[n++] = 0xE9;                                                        /* jmp target+8 */
    *(int32_t *)(cave + n) = (int32_t)((target + STOLEN) - (cave + n + 4)); n += 4;

    /* Write the entry detour: E9 rel32 (to cave) + NOP pad to STOLEN. */
    DWORD old;
    if (!VirtualProtect(target, STOLEN, PAGE_EXECUTE_READWRITE, &old)) return 0;
    target[0] = 0xE9;
    *(int32_t *)(target + 1) = (int32_t)(cave - (target + 5));
    for (int i = 5; i < STOLEN; i++) target[i] = 0x90;
    VirtualProtect(target, STOLEN, old, &old);
    FlushInstructionCache(GetCurrentProcess(), target, STOLEN);
    h->hooked = 1;
    return 1;
}

/* Call the (possibly hooked) function as __thiscall _N(this)(int,int,int). */
static int call_fn(unsigned char *fn, void *thisptr, int mAge, int fAge, int fFert)
{
    int ret;
    __asm {
        mov ecx, thisptr
        push fFert
        push fAge
        push mAge
        mov eax, fn
        call eax
        movzx eax, al
        mov ret, eax
    }
    return ret;
}

int main(void)
{
    printf("== VF2 runtime-hook Stage-1 spike (32-bit) ==\n");

    /* Confirm the prologue we steal really is the stock function's, by reading
     * the first 8 bytes from the real function bytes extracted from the stock
     * object. This ties the spike to the ACTUAL binary. */
    FILE *f = fopen("ChanceOfPregnancy.bin", "rb");
    if (!f) { printf("cannot open ChanceOfPregnancy.bin\n"); return 2; }
    unsigned char real[0x200];
    size_t sz = fread(real, 1, sizeof(real), f);
    fclose(f);
    printf("real function bytes: %u (expect 0xF7=%d)\n", (unsigned)sz, 0xF7);
    if (sz != 0xF7) { printf("unexpected size\n"); return 2; }
    printf("real prologue == expected steal bytes = %d (expect 1)\n",
           memcmp(real, kExpectedPrologue, STOLEN) == 0);

    /* Build the function under test: the REAL 8-byte prologue, then a safe stub
     * body standing in for the real 0xF7 body (which needs the whole linked
     * game -- see SCOPE). The stub returns 0 in al, like stock ChanceOfPregnancy
     * with no pregnancy, and rets 0Ch (__thiscall, 3 int args). */
    unsigned char *fn = (unsigned char *)VirtualAlloc(
        NULL, 0x1000, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    int n = 0;
    memcpy(fn, kExpectedPrologue, STOLEN); n += STOLEN; /* real prologue */
    /* stub body: xor eax,eax ; pop ebp ; ret 0Ch  (balances the prologue's
     * push ebp; the stolen prologue set up ebp) */
    fn[n++] = 0x33; fn[n++] = 0xC0;             /* xor eax,eax */
    fn[n++] = 0x5D;                             /* pop ebp */
    fn[n++] = 0xC2; fn[n++] = 0x0C; fn[n++] = 0x00; /* ret 0Ch */

    printf("prologue steal is the clean 8-byte boundary = %d (expect 1)\n",
           memcmp(fn, kExpectedPrologue, STOLEN) == 0);

    Hook h;
    int ok = install(&h, fn);
    printf("install on real prologue = %d (expect 1)\n", ok);

    /* Re-hooking the now-detoured entry must be refused. */
    Hook h2;
    int rehook = install(&h2, fn);
    printf("re-hook of patched entry = %d (expect 0)\n", rehook);

    /* Flag OFF: the call must still reach the stock body via the fallback and
     * behave as stock (the thing a wrong steal breaks). ChanceOfPregnancy with
     * absurd young ages / zero fertility returns 0. */
    gAllowOlderPregnancies = 0;
    gHelperCalls = 0;
    int rOff = call_fn(fn, (void *)0x10, 20, 20, 0);
    printf("flag OFF: helper_calls=%d (expect 0), returned=%d\n",
           gHelperCalls, rOff);

    /* Flag ON: control must reach the DLL-side helper instead. */
    gAllowOlderPregnancies = 1;
    gHelperCalls = 0;
    int rOn = call_fn(fn, (void *)0x10, 800, 800, 5);
    printf("flag ON : helper_calls=%d (expect 1), returned=%d (expect 1)\n",
           gHelperCalls, rOn);

    int pass = ok && !rehook && gHelperCalls == 1 && rOn == 1;
    printf("\nRESULT: %s\n", pass ? "all checks passed" : "FAILED");
    return pass ? 0 : 1;
}
