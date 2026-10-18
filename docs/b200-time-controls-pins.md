# B200 Time Controls: pins and layout decision (static, no live test)

Evidence: capstone + pefile against two files.
- Vanilla: `C:\vf2w\_vanilla_rt\Virtual Families 2.exe`
- B200 core: `C:\vf2w\vf2\outputs\VF2-B200-matrix-core\Virtual Families 2 - B200.exe` (the B200 link output of `patch_mobile_furniture_pack.py`, core variant; there is no other B200 exe on disk to use)

## 1. Pins proved on the B200 core exe

| Item | Address | Proof |
|---|---|---|
| theOptionsDialog ctor | 0x4A5D00 .. 0x4A6247 (`ret 8`) | `mov [ebx],0x5006D8` at 0x4A5D34; epilogue `ret 8` at 0x4A6247 |
| vtable | 0x5006D8 | slots read from the file: 0=0x4A6260, 1=0x4A6B60, 2=0x403B40, 3=0x4A6940, 4=0x4739A0, 5=0x473850; also stored again at 0x4A6252 (dtor path) |
| slot-3 HandleMessage | 0x4A6940 | `cmp [ebp+8],8` (msg 8 = button) then compares id in edi to `[esi+0x74]` (Done, 2), `[esi+0x78]` (3), `[esi+0x7C]` (Evict, 4), then `edi-5 <= 3` for the four checkbox ids 5..8 (checks `[eax+0x25B07..0x25B0A]`), epilogue `ret 8` at 0x4A6B43 |
| button ids set in ctor | 0x4A5D5D / 5D64 / 5D6B | `[ebx+0x74]=2`, `[ebx+0x78]=3`, `[ebx+0x7C]=4` |
| AddControl | 0x47EC70 (`this`=dialog, one arg) | called after each button |
| SetChecked | 0x47EA50 (`ret`-less thiscall helper: `mov ecx,[ecx+0x10]; mov [ecx+0x31],al`) | last call is 0x4A621B (the 4th checkbox, id 8) |
| button ctor | 0x472D70 (`push id`, `push image`) | used for Done (0x4A5F4B) and Evict (0x4A6028) |
| image lookup | 0x49B1D0 (`ecx` = image manager; args 0x128, x, y, parent, 0) | used identically for Done and Evict |
| aging | call 0x4C4DEF -> IncrementAge 0x4C4080 (`add [ecx],eax`) | disassembled; `push eax` holds the computed age delta |
| GameState Load / Save | 0x499DC0 / 0x49AA00 | prologues disassembled (Load allocates 0x25BAC) |

## 2. Vanilla counterpart (the part the B200 ctor was compiled from)

- Vanilla vtable 0x4E2704: slot 1 = 0x422420, slot 3 = 0x422900. Ctor 0x4217E0 .. 0x421D14 (`ret 8`); vtable store at 0x421814.
- Last SetChecked call 0x421CEB (`call 0x40C8F0`; 0x40C8F0 = `mov eax,[ecx+0x10]; mov cl,[esp+4]; mov [eax+0x31],cl; ret 4`), the same helper as B200 0x47EA50 (the "Settings button stub" address).
- Vanilla Evict guard: `cmp [0x5ACFC8],ebx; jne 0x421B38` at 0x421AA9 and `cmp [0x5ACFCC],2; jge 0x421B38` at 0x421AB5, so the Evict block is skipped unless the generation flags allow it. Evict is built at 0x421ABE..0x421B33 with `ecx=0x1D2`, y = height - 0x1E - Done height, image 0x128, id `[esi+0x7C]`.
- The vanilla block never calls AddControl for Evict; B200 inserts it.

## 3. B200 Evict construction (what the generator does)

`patch_options_dialog` (generator line 40586) NOPs the first guard (6-byte `jne`, now 0x4A5FDA..0x4A5FDF) and the second (2-byte `jge`, now 0x4A5FE7..0x4A5FE8; the `cmp`s at 0x4A5FD3 and 0x4A5FE0 are left in place), and inserts `push esi; mov ecx,ebx; call AddControl` at ctor + 0x360 = 0x4A6060 (disassembly confirms `push esi / mov ecx,ebx / call 0x47EC70`). Result in B200:

- 0x4A5FE9 `push 0x14; call 0x4CE840` (allocate the 0x14-byte button)
- 0x4A6000..0x4A6018: `push 0 / push ebx / push (height - 0x1E - doneH) / push 0x1D2 / push 0x128`, `call 0x49B1D0`
- 0x4A6023 `push [ebx+0x7C]` (id 4); 0x4A6028 `call 0x472D70`
- 0x4A603D..0x4A6058 label: string id 0x10 via `0x4A8940`
- 0x4A6060..0x4A6063 AddControl.

## 4. Layout (scene-local coordinates)

The dialog is 0x280 x 0x1F2 = 640 x 498 (`push 0x1F2 / push 0x280` at 0x4A5E00..0x4A5E05; centring maths at 0x4A5E6A, 0x4A5E9B uses the same constants).

| Button | x | y | Source |
|---|---|---|---|
| Done (id 2) | (640 - W)/2 = 248, so W = 144 | 498 - 30 - H = 434, so H = 34 | placed via vtable `[edx+4]` at 0x4A5FA1 with x = `(sceneW - btnW)/2`, y = `sceneH - btnH - 0x1E` |
| Evict (id 4) | 0x1D2 = 466 | same y formula as Done = 434 | 0x4A6000..0x4A6013 |

The button width/height (144x34) are derived from REDUX's recorded Done position (248,434), not read from the art file; they are consistent with the code (640 - 466 - 144 = 30 margin to the right edge, 30 above the bottom).

Other controls: four checkboxes ids 5..8 at x = 0x10B / 0x163 / 0x1BB / 0x213, y = `[ebx+0x8C] + 0x4B` (screen top + 75), nowhere near y=434.

## 5. Decision

Time Controls button: **x = 30, y = 434**, same art/id-0x128 as Done and Evict. Evidence:
- It mirrors Evict (right edge 610, margin 30): left edge 30, right edge 174.
- Gaps: Time 174 -> Done 248 = 74; Done right 392 -> Evict 466 = 74. Symmetric, no overlap with Done, Evict or the checkbox row.
- Same y expression as Done and Evict, so it needs no new arithmetic: constants 0x1E (x=0x1E=30) and 0x1D2 were already in the code.

New button id: **9** (2, 3, 4 and 5..8 are used; the handler's `edi-5 <= 3` test sends ids above 8 to the fall-through at 0x4A6B1C, so id 9 reaches no existing branch). It must be matched in slot 3 (0x4A6940) before the Evict compare chain.

## 6. The companion DLL (added after the static study)

`runtime/native/b200time/` builds `vf2time_b200.dll` (`runtime/native/build_b200time.bat`, /W4 /WX). It is
REDUX's Settings-screen Time Controls module (`vf2fun_time.inc`) re-proved against this executable and made
self-contained (its own small plan / pin / apply host; one feature, one DLL). Every address is in
`runtime/b200_time_sites.py` (46 pins), proved by `runtime/tools/gen_b200_time_sites.py` (capstone + pefile) and
emitted as `b200time_sites.h`.

Findings that differ from the vanilla runtime build:

- **The B200 image is relocated.** `DllCharacteristics = 0x8140` (DYNAMICBASE) with a `.reloc` section, so
  Windows may load it away from 0x400000. The DLL rebases every address by (module base - 0x400000) and each pin
  compares the live bytes with every relocated 32-bit field (named by the `.reloc` table) taken back to its
  link-time value. The vanilla runtime build never needed this (no ASLR).
- Game state: the `theGameState` singleton pointer is `[0x685A88]` (`Get` at 0x499620), the speed field is still
  `+0x25B18`, `GameTime` is 0x683038, `CGameTime::SetSpeed` is 0x468B80, the villager manager is 0x706F90 with
  the vanilla array offset 0x1CC70 / stride 0x1CC0C / age +0x6A54 / health +0x6B00 / active +0x1BB84 / left home
  +0x1BB88 (all re-proved, not assumed).
- Pause leaves `CGameTime` at speed 0, not 999 (`SetSpeed(999)` stores 0 in B200 and in vanilla); the speed field
  carries the +999.
- The constructor stub finds the dialog in **ebx** (vanilla's was esi): `esi` is the last check box.
- `theGameState::Save` / `Load` are vtable slots 14 / 13 at 0x4FC58C / 0x4FC588 (functions 0x49AA00 / 0x499DC0).
- Aging: B200 stores the native tick count in `[ebp-14h]` before its single `call IncrementAge` (0x4C4DEF), and
  computes the accumulator remainder from it, so the module retargets that one call (no stolen bytes).
- The button is placed at x = 30 (0x1E, the literal), y = dialog height - Done height - 0x1E, id 9.

Tests: `tests/test_b200_time_controls.py` runs the REAL compiled DLL together with the REAL B200 core code inside
unicorn (`tests/b200_time_emu.py`, `tests/b200_time_scenarios.py`), at the link address and relocated by 0x1A0000.
The emulator test build leaves out `ISOLATION_AWARE_ENABLED` (Microsoft's activation-context wrappers around the
user32 calls); the shipped build has it, exactly as REDUX's.

## 7. Not covered

- No live test. The art behind the buttons at (30,434) is unverified (REDUX uses the same spot), and the button
  width/height (144 x 34) come from REDUX's recorded Done position, not the art file. The scenarios feed those
  sizes to the real constructor code through a stand-in Done button.
- How the DLL is loaded into the B200 process (a loader stub / entry point calling `B200Time_Startup`) and the
  patcher UI that writes `vf2time.ini` (`[Patches] TimeControls=1`) are not part of this change.
- The shipped build's isolation-aware activation of the dialog's manifest, the SDL fullscreen toggle and real
  Windows dialog behaviour are not exercised under emulation.
- No 32-variant matrix has been built; other variants' constructor / `theGameState` / aging code may differ from
  the core variant, in which case the pins refuse and nothing is installed.
