#!/usr/bin/env python3
"""Assemble the executable's loader stub into runtime/stub.json.

The stub is the ONLY code added to the executable. It has one entry point:

* init_entry -- theGame's vtable slot for Init (0x4E29A8) points here. theGame
  ::Init is called exactly once, at startup, before the game loop runs. The
  entry saves every register, runs the loader once, calls VF2Fun_Startup() if
  the DLL exported it, restores every register and jumps to the real theGame
  ::Init (0x428620), so Init sees exactly the state the game gave it.

The loader builds "<exe folder>\\Virtual Families 2 Patcher Files\\vf2fun.dll"
from GetModuleFileNameW and loads it with LoadLibraryW, both resolved through
the GetModuleHandleA/GetProcAddress imports the vanilla game already has. It
never loads a bare DLL name and never runs from DllMain. Any failure (no
kernel32 export, path too long, DLL missing, export missing) leaves the game
stock: state records the failure and init_entry still jumps to theGame::Init.

Data (separate read-write section, never executable):
  +0  state        0 = not run, 2 = failed/in progress, 1 = DLL loaded
  +4  VF2Fun_Startup address (0 if missing)
  +8  the DLL's HMODULE (read by the live probe; 0 if not loaded)
  +12 reserved
  +16 UTF-16 path buffer, 1024 characters

usage: build_stub.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from keystone import KS_ARCH_X86, KS_MODE_32, Ks

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))
import vf2_runtime_sites as S  # noqa: E402

OUT = RUNTIME / "stub.json"
PATH_CHARS = 1024
CODE_VA = S.STUB_CODE_VA
DATA_VA = S.STUB_DATA_VA
STATE, FN_STARTUP, MODULE, PATH = DATA_VA, DATA_VA + 4, DATA_VA + 8, DATA_VA + 16
STRINGS = CODE_VA + 0x200
SUFFIX = S.PATCHER_FOLDER + "\\" + S.DLL_NAME


def build() -> dict:
    strings = [
        ("kernel32", b"kernel32.dll\0"),
        ("gmfnw", b"GetModuleFileNameW\0"),
        ("llw", b"LoadLibraryW\0"),
        ("startup", b"VF2Fun_Startup\0"),
        ("suffix", SUFFIX.encode("utf-16-le") + b"\0\0"),
    ]
    addr, blob = {}, b""
    for key, raw in strings:
        if len(blob) % 2:
            blob += b"\0"
        addr[key] = STRINGS + len(blob)
        blob += raw
    asm = f"""
    init_entry:
        pushfd
        pushad
        call loader
        mov eax, dword ptr [{FN_STARTUP:#x}]
        test eax, eax
        jz init_done
        call eax
    init_done:
        popad
        popfd
        jmp {S.INIT_SLOT_EXPECTED:#x}

    loader:
        cmp dword ptr [{STATE:#x}], 0
        jne loader_done
        mov dword ptr [{STATE:#x}], 2
        push {addr['kernel32']:#x}
        call dword ptr [{S.IAT_GET_MODULE_HANDLE_A:#x}]
        test eax, eax
        jz loader_done
        mov esi, eax
        push {addr['gmfnw']:#x}
        push esi
        call dword ptr [{S.IAT_GET_PROC_ADDRESS:#x}]
        test eax, eax
        jz loader_done
        push {PATH_CHARS - 64}
        push {PATH:#x}
        push 0
        call eax
        test eax, eax
        jz loader_done
        cmp eax, {PATH_CHARS - 64}
        jae loader_done
        lea ecx, [{PATH:#x} + eax*2]
    back:
        sub ecx, 2
        cmp ecx, {PATH:#x}
        jb loader_done
        cmp word ptr [ecx], 0x5c
        jne back
        add ecx, 2
        mov edx, {addr['suffix']:#x}
    copy:
        mov ax, word ptr [edx]
        mov word ptr [ecx], ax
        add edx, 2
        add ecx, 2
        test ax, ax
        jnz copy
        push {addr['llw']:#x}
        push esi
        call dword ptr [{S.IAT_GET_PROC_ADDRESS:#x}]
        test eax, eax
        jz loader_done
        push {PATH:#x}
        call eax
        test eax, eax
        jz loader_done
        mov dword ptr [{MODULE:#x}], eax
        push {addr['startup']:#x}
        push eax
        call dword ptr [{S.IAT_GET_PROC_ADDRESS:#x}]
        mov dword ptr [{FN_STARTUP:#x}], eax
        mov dword ptr [{STATE:#x}], 1
    loader_done:
        ret
    """
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    code, _ = ks.asm(asm, CODE_VA)
    code = bytes(code)
    if len(code) > STRINGS - CODE_VA:
        raise SystemExit("stub too large")
    payload = code + b"\xCC" * (STRINGS - CODE_VA - len(code)) + blob
    return {
        "code_va": hex(CODE_VA),
        "data_va": hex(DATA_VA),
        "data_size": 16 + PATH_CHARS * 2,
        "init_entry": hex(CODE_VA),
        "code_length": len(code),
        "strings_va": hex(STRINGS),
        "code": payload.hex(),
    }


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=1) + "\n", newline="\n")
    print("wrote", OUT)
