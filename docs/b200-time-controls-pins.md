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

## 6. Not covered

- The art behind the buttons at (30,434): no live look, so whether the dialog background is blank there is unverified (REDUX uses the same spot).
- Button width/height not read from the image file.
- No DLL, no 32-variant matrix built.
