"""The Translations DLL (vf2tr_b200.dll) installing and the game's own text code running, under emulation.

The REAL executable (the B200 core, or any later matrix build) and the REAL compiled test DLL share one emulated
address space (tests/b200_time_emu.py). Game code that runs for real, at the link address or relocated:
theStringManager::GetString and GetStringFromNameGenderTemplate (the lookup and the template filler: the record's
override, the person choice, the buffer size), and the C runtime's strncpy, strncat and sprintf, whose entries the DLL
replaces by guards. The DLL's own compiled code runs for real too (B200Tr_TestInstall: resolve the pinned runs, build
the manager, read the translation, install the guards, set the overrides).

Seams (recorded, never real): theStringManager::Get (it would build the manager from files; the seam fills the index
the constructor's first loop builds, from the real table), the Win32 imports of the DLL (VirtualAlloc, VirtualProtect,
FlushInstructionCache, the heap, the module handle) and the DLL's own pattern scan (the same search, done in Python).

Nothing here starts the game, and nothing writes the executable on disk.
"""
from __future__ import annotations

import os
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "runtime" / "tools"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
import b200_translations_sites as S  # noqa: E402
import gen_b200_translations_sites as G  # noqa: E402
import vf2_translation_format as tf  # noqa: E402

from b200_time_emu import DLL_BASE, Emu  # noqa: E402

PAGE_EXECUTE_READWRITE = 0x40


class World:
    """One emulated process: an executable + the test DLL, the string manager 'built'."""

    def __init__(self, exe, dll, *, delta=0, core=None):
        self.e = e = Emu(exe, dll, delta)
        self.delta = delta
        core_bytes = Path(core).read_bytes() if core else None
        self.exe = G.Exe(Path(exe).read_bytes())
        self.sites = G.resolve(self.exe, G.Exe(core_bytes) if core_bytes else None)
        self.protect_calls = []      # (address, size, protection, order)
        self.code_writes = []        # addresses written inside the executable after install began
        self.order = 0
        self.manager_built = 0
        self.table_va = self.sites["TABLE"]
        self.index_va = self.sites["INDEX"]
        self.max_id = self.sites["MAX_ID"]
        self.count = self.sites["COUNT"]
        self._imports()
        self._seams()

    # ------------------------------------------------------------------ addresses
    def live(self, link_va):
        return link_va + self.delta

    def site(self, name):
        return self.sites[name.upper()] + self.delta

    # ------------------------------------------------------------------ the game's table, read in Python
    def records(self):
        """(id, key, text, address) of every record of the table, as the executable holds it (unrelocated link
        addresses; the emulated memory is relocated by delta)."""
        out = []
        for k in range(self.count):
            va = self.live(self.table_va) + 16 * k
            id_, key, text, ov = struct.unpack("<IIII", self.e.read(va, 16))
            if id_ == 0 and key == 0:
                continue
            out.append((id_, self.e.cstr(key), self.e.read_cstr_bytes(text) if hasattr(self.e, "read_cstr_bytes")
                        else self._bytes(text), va))
        return out

    def _bytes(self, addr):
        out = b""
        while True:
            c = self.e.read(addr, 1)
            if c == b"\0":
                return out
            out += c
            addr += 1

    def english(self, string_id):
        for id_, _key, text, _va in self.records():
            if id_ == string_id:
                return text.decode("cp1252")
        raise KeyError(string_id)

    # ------------------------------------------------------------------ imports and seams
    def _imports(self):
        e = self.e

        def virtual_alloc(emu):
            size = emu.arg(1)
            return emu.alloc(size), 16

        def virtual_protect(emu):
            self.order += 1
            addr, size, prot, old = emu.arg(0), emu.arg(1), emu.arg(2), emu.arg(3)
            self.protect_calls.append((addr, size, prot, self.order))
            if old:
                emu.w32(old, 4)
            return 1, 16

        e.imports.update({
            "VirtualAlloc": virtual_alloc,
            "VirtualProtect": virtual_protect,
            "FlushInstructionCache": lambda emu: (1, 12),
            "GetCurrentProcess": lambda emu: (0xFFFFFFFF, 0),
            "GetProcessHeap": lambda emu: (1, 0),
            "HeapAlloc": lambda emu: (emu.alloc(emu.arg(2) + 16), 12),
            "GetModuleHandleW": self._get_module_handle,
        })

    def _get_module_handle(self, emu):
        name = emu.arg(0)
        if name == 0:
            return emu.base, 4
        return 0, 4                       # any other module (the Unicode DLLs) is not loaded here

    def _seams(self):
        e = self.e
        # the DLL's own scan, done in Python (an emulated byte-by-byte scan of the whole image is slow)
        scan_at = e.call(e.dll_export("B200Tr_TestScanAddress"))

        def scan(emu):
            base, size, pat, mask, length, hits = (emu.arg(i) for i in range(6))
            data = emu.read(base, size)
            p, m = emu.read(pat, length), emu.read(mask, length)
            rx = re.compile(b"".join(b"." if w else re.escape(bytes([b])) for b, w in zip(p, m)), re.DOTALL)
            first, count = 0, emu.r32(hits)
            for mt in rx.finditer(data):
                if not count:
                    first = base + mt.start()
                count += 1
                if count >= 2:
                    break
            emu.w32(hits, count)
            return first, 0
        e.seam_live(scan_at, scan)

        def manager_get(emu):
            # theStringManager's constructor, first loop: index[id] = the first record with that id, else 0
            first = {}
            for id_, _key, _text, va in self.records():
                first.setdefault(id_, va)
            for i in range(1, self.max_id):
                e.w32(self.live(self.index_va) + 4 * i, first.get(i, 0))
            self.manager_built += 1
            return 0x1000, 0
        e.seam_live(self.site("string_manager_get"), manager_get)

    # ------------------------------------------------------------------ the DLL
    def install(self, text: bytes, unicode_active=False) -> int:
        e = self.e
        buf = e.alloc(len(text) + 16)
        e.write(buf, text)
        status = e.call(e.dll_export("B200Tr_TestInstall"), (buf, len(text), 1 if unicode_active else 0))
        return struct.unpack("<i", struct.pack("<I", status))[0]

    def log(self) -> str:
        e = self.e
        return e.cstr(e.call(e.dll_export("B200Tr_TestLog")))

    def status(self) -> dict:
        e = self.e
        a = e.dll_export("B200Tr_Status")
        keys = ("magic", "version", "requested", "resolved", "installed", "used", "refused", "guarded", "textMode",
                "patchLines")
        return {k: e.r32(a + 4 * i) for i, k in enumerate(keys)}

    # ------------------------------------------------------------------ the game's functions
    def get_string(self, string_id: int) -> bytes:
        e = self.e
        p = e.call(self.site("get_string"), (string_id,))
        return self._bytes(p)

    def get_string_ptr(self, string_id: int) -> int:
        return self.e.call(self.site("get_string"), (string_id,))

    def fill(self, string_id: int, size: int = 256, name=b"Zo\xeb", sex=0, award=7, name2=b"Max", sex2=0) -> bytes:
        e = self.e
        dst = e.alloc(size + 16, 0x7E)
        n1, n2 = e.alloc(64), e.alloc(64)
        e.write(n1, name + b"\0")
        e.write(n2, name2 + b"\0")
        e.call(self.site("fill_template"), (dst, size, string_id, n1, sex, award, n2, sex2))
        out = self._bytes(dst)
        assert len(out) < size, "the template filler wrote past its buffer"
        assert e.read(dst + size, 16) == b"\x7E" * 16, "the template filler wrote past its buffer"
        return out

    def strncpy(self, src_ptr: int, n: int, size: int = 2048) -> bytes:
        e = self.e
        dst = e.alloc(size, 0x7E)
        e.call(self.site("strncpy"), (dst, src_ptr, n))
        assert e.read(dst + n, 8) == b"\x7E" * 8, "strncpy wrote past its count"
        return e.read(dst, n)

    def strncat(self, src_ptr: int, n: int, prefix=b"") -> bytes:
        e = self.e
        dst = e.alloc(2048, 0x7E)
        e.write(dst, prefix + b"\0")
        e.call(self.site("strncat"), (dst, src_ptr, n))
        return self._bytes(dst)

    def sprintf(self, fmt_ptr: int, *args) -> bytes:
        e = self.e
        dst = e.alloc(4096, 0x7E)
        e.call(self.site("sprintf"), (dst, fmt_ptr, *args))
        return self._bytes(dst)

    def cstring(self, data: bytes) -> int:
        p = self.e.alloc(len(data) + 2)
        self.e.write(p, data + b"\0")
        return p

    def table_overrides(self) -> list[int]:
        return [self.e.r32(va + 12) for _id, _k, _t, va in self.records()]

    def entry_bytes(self, name: str, n: int = 8) -> bytes:
        return self.e.read(self.site(name), n)


def make_file(world: World, translations: dict[int, str], *, code="fr", language="Français", translator="(TEST)",
              game=None) -> bytes:
    """A translation file (UTF-8 with a BOM) for the executable's own table: id -> translation."""
    entries = []
    english = {}
    for id_, _key, text, _va in world.records():
        english.setdefault(id_, text.decode("cp1252"))
    for id_ in translations:
        entries.append(tf.Entry(tf.make_key("strings", str(id_), english[id_]), english[id_]))
    f = tf.new_file("vf2", entries, language, code, translator)
    for row, id_ in zip(f.rows, translations):
        row.translation = translations[id_]
    data = tf.to_bytes(f)
    if game is not None:
        data = data.replace(b"@game\tVirtual Families 2", b"@game\t" + game.encode())
    return data
