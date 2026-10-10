#!/usr/bin/env python3
"""Stage 1 runtime-hook patcher: build a patched COPY of vanilla Virtual Families 2.

    vf2_runtime_patcher.py apply --game-dir VANILLA --output-dir NEW
        [--dll runtime/build/vf2fun.dll] [--allow-older-pregnancies]
        [--exe-name "VF2 Runtime Test.exe"]

The source game folder is only read. Everything is written to a new, empty
output folder outside it. The executable gets the minimal bootstrap and
nothing else:

* .vf2fun (read + execute, new section): the loader stub from stub.json.
* .vf2fud (read + write, new section): the stub's state and path buffer. No
  page is both writable and executable.
* theGame's vtable slot for Init (0x4E29A8) points at the stub instead of
  theGame::Init (0x428620); the stub jumps there after loading the DLL.
* PE header: section count, SizeOfImage, checksum.

No code cave is added to any existing section and no other byte of the
executable changes. Every trampoline, detour and all feature logic is in
"<output>\\Virtual Families 2 Patcher Files\\vf2fun.dll", which installs its
hooks at runtime. vf2fun.ini beside it holds the setting
([Patches] AllowOlderPregnancies=0/1). A missing DLL, ini or setting is the
stock game.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNTIME))
import vf2_runtime_sites as S  # noqa: E402

STUB = RUNTIME / "stub.json"
DEFAULT_DLL = RUNTIME / "build" / S.DLL_NAME
CODE_SECTION = ".vf2fun"
DATA_SECTION = ".vf2fud"
CODE_CHARACTERISTICS = 0x60000020  # code | execute | read
DATA_CHARACTERISTICS = 0xC0000040  # initialized data | read | write


class PatchError(RuntimeError):
    pass


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


class PE:
    def __init__(self, data: bytes):
        self.data = bytearray(data)
        d = self.data
        self.pe = struct.unpack_from("<I", d, 0x3C)[0]
        if bytes(d[self.pe:self.pe + 4]) != b"PE\0\0":
            raise PatchError("not a PE image")
        self.nsec_off = self.pe + 6
        self.opt = self.pe + 24
        self.optsz = struct.unpack_from("<H", d, self.pe + 20)[0]
        self.base = struct.unpack_from("<I", d, self.opt + 28)[0]
        self.sect_align, self.file_align = struct.unpack_from("<II", d, self.opt + 32)

    @property
    def nsec(self) -> int:
        return struct.unpack_from("<H", self.data, self.nsec_off)[0]

    def sections(self):
        out = []
        for i in range(self.nsec):
            o = self.opt + self.optsz + i * 40
            name = bytes(self.data[o:o + 8]).rstrip(b"\0").decode("ascii", "replace")
            vsize, va, rsize, raw = struct.unpack_from("<IIII", self.data, o + 8)
            chars = struct.unpack_from("<I", self.data, o + 36)[0]
            out.append((name, va, vsize, raw, rsize, chars))
        return out

    def offset(self, va: int) -> int:
        rva = va - self.base
        for _n, sva, vsize, raw, rsize, _c in self.sections():
            if sva <= rva < sva + min(max(vsize, rsize), rsize):
                return raw + rva - sva
        raise PatchError(f"address {va:#x} is not in the file")

    def next_section_va(self) -> int:
        last = self.sections()[-1]
        return self.base + _align(last[1] + max(last[2], last[4]), self.sect_align)

    def add_section(self, name: str, payload: bytes, characteristics: int) -> int:
        hdr = self.opt + self.optsz + self.nsec * 40
        first_raw = min(s[3] for s in self.sections() if s[3])
        if hdr + 40 > first_raw:
            raise PatchError("no room for another section header")
        if any(self.data[hdr:hdr + 40]):
            raise PatchError("section header slot is not empty")
        va = self.next_section_va()
        raw = _align(len(self.data), self.file_align)
        rsize = _align(len(payload), self.file_align)
        self.data.extend(b"\0" * (raw - len(self.data)))
        self.data.extend(payload + b"\0" * (rsize - len(payload)))
        struct.pack_into("<8sIIIIIIHHI", self.data, hdr, name.encode().ljust(8, b"\0"),
                         len(payload), va - self.base, rsize, raw, 0, 0, 0, 0, characteristics)
        struct.pack_into("<H", self.data, self.nsec_off, self.nsec + 1)
        struct.pack_into("<I", self.data, self.opt + 56,
                         _align(va - self.base + len(payload), self.sect_align))
        return va

    def update_checksum(self) -> None:
        off = self.opt + 64
        struct.pack_into("<I", self.data, off, pe_checksum(bytes(self.data), off))


def pe_checksum(data: bytes, checksum_offset: int) -> int:
    """The PE checksum of `data`, ignoring the stored checksum field."""
    buf = bytearray(data)
    struct.pack_into("<I", buf, checksum_offset, 0)
    total = 0
    d = bytes(buf) + b"\0" * (len(buf) % 2)
    for (word,) in struct.iter_unpack("<H", d):
        total += word
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + len(buf)) & 0xFFFFFFFF


def load_stub() -> dict:
    return json.loads(STUB.read_text())


def patch_executable(vanilla: bytes) -> bytes:
    """Return the patched executable bytes."""
    if hashlib.sha256(vanilla).hexdigest() != S.VANILLA_SHA256:
        raise PatchError("this is not the vanilla Virtual Families 2 executable")
    stub = load_stub()
    code_va, data_va = int(stub["code_va"], 16), int(stub["data_va"], 16)
    if (code_va, data_va) != (S.STUB_CODE_VA, S.STUB_DATA_VA):
        raise PatchError("stub.json was built for different section addresses")
    pe = PE(vanilla)
    if pe.base != S.IMAGE_BASE:
        raise PatchError("unexpected image base")
    if any(s[0] in (CODE_SECTION, DATA_SECTION) for s in pe.sections()):
        raise PatchError("the executable is already patched")
    slot = pe.offset(S.INIT_SLOT)
    if struct.unpack_from("<I", pe.data, slot)[0] != S.INIT_SLOT_EXPECTED:
        raise PatchError("unexpected theGame::Init vtable slot")
    if pe.next_section_va() != code_va:
        raise PatchError("the stub was built for a different section address")
    pe.add_section(CODE_SECTION, bytes.fromhex(stub["code"]), CODE_CHARACTERISTICS)
    if pe.add_section(DATA_SECTION, bytes(stub["data_size"]), DATA_CHARACTERISTICS) != data_va:
        raise PatchError("data section landed at an unexpected address")
    struct.pack_into("<I", pe.data, slot, int(stub["init_entry"], 16))
    pe.update_checksum()
    return bytes(pe.data)


def write_settings(path: Path, allow_older_pregnancies: bool) -> None:
    path.write_text(
        "; Virtual Families 2 runtime add-ons (Stage 1). 1 = on, anything else = off.\n"
        "[Patches]\n"
        f"AllowOlderPregnancies={1 if allow_older_pregnancies else 0}\n",
        encoding="utf-16",
    )


def apply(game_dir: Path, output_dir: Path, dll: Path, allow_older_pregnancies: bool,
          exe_name: str | None = None) -> Path:
    game_dir, output_dir = game_dir.resolve(), output_dir.resolve()
    if output_dir == game_dir or game_dir in output_dir.parents or output_dir in game_dir.parents:
        raise PatchError("the output folder must be a new folder outside the game folder")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise PatchError(f"output folder is not empty: {output_dir}")
    if not dll.is_file():
        raise PatchError(f"companion DLL not found: {dll} (build it with runtime\\native\\build.bat)")
    exe = game_dir / S.VANILLA_EXE_NAME
    patched = patch_executable(exe.read_bytes())
    shutil.copytree(game_dir, output_dir, dirs_exist_ok=True)
    target = output_dir / (exe_name or S.VANILLA_EXE_NAME)
    if exe_name and exe_name != S.VANILLA_EXE_NAME:
        (output_dir / S.VANILLA_EXE_NAME).unlink()
    target.write_bytes(patched)
    files = output_dir / S.PATCHER_FOLDER
    files.mkdir(exist_ok=True)
    shutil.copy2(dll, files / S.DLL_NAME)
    write_settings(files / S.INI_NAME, allow_older_pregnancies)
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--game-dir", required=True, type=Path)
    a.add_argument("--output-dir", required=True, type=Path)
    a.add_argument("--dll", type=Path, default=DEFAULT_DLL)
    a.add_argument("--allow-older-pregnancies", action="store_true")
    a.add_argument("--exe-name", help="name for the patched executable (test builds get their own save folder)")
    args = ap.parse_args()
    try:
        exe = apply(args.game_dir, args.output_dir, args.dll, args.allow_older_pregnancies, args.exe_name)
    except PatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"patched: {exe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
