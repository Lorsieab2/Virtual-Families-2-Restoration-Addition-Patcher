from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct


IMAGE_REL_I386_DIR32 = 0x0006


@dataclass
class Section:
    index: int
    header_off: int
    name: str
    raw_size: int
    raw_ptr: int
    reloc_ptr: int
    nreloc: int


@dataclass
class Symbol:
    index: int
    off: int
    name: str
    value: int
    section: int
    aux: int


class CoffObject:
    def __init__(self, path: Path):
        self.path = path
        self.buf = bytearray(path.read_bytes())
        self._parse()

    def _name_at(self, pos: int) -> str:
        raw = self.buf[pos : pos + 8]
        zeroes, str_off = struct.unpack_from("<II", raw, 0)
        if zeroes == 0 and 0 <= str_off < len(self.strtab):
            end = self.strtab.find(b"\0", str_off)
            if end < 0:
                end = len(self.strtab)
            return self.strtab[str_off:end].decode("ascii", "replace")
        return raw.split(b"\0", 1)[0].decode("ascii", "replace")

    def _parse(self):
        self.machine, self.nsects, self.timestamp, self.symptr, self.nsyms, self.opthdr, self.chars = struct.unpack_from("<HHIIIHH", self.buf, 0)
        self.sections = []
        off = 20 + self.opthdr
        for i in range(1, self.nsects + 1):
            raw_name = self.buf[off : off + 8]
            name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
            raw_size, raw_ptr, reloc_ptr, nreloc = struct.unpack_from("<Ixx??", b"\0" * 8, 0) if False else (None, None, None, None)
            virt_size, virt_addr, raw_size, raw_ptr, reloc_ptr, line_ptr, nreloc, nline, characteristics = struct.unpack_from("<IIIIIIHHI", self.buf, off + 8)
            self.sections.append(Section(i, off, name, raw_size, raw_ptr, reloc_ptr, nreloc))
            off += 40
        self.strtab_ptr = self.symptr + self.nsyms * 18
        self.strtab_size = struct.unpack_from("<I", self.buf, self.strtab_ptr)[0]
        self.strtab = bytes(self.buf[self.strtab_ptr : self.strtab_ptr + self.strtab_size])

        self.symbols = []
        pos = self.symptr
        idx = 0
        while idx < self.nsyms:
            name = self._name_at(pos)
            value, sectnum, typ, storage, aux = struct.unpack_from("<IhHBB", self.buf, pos + 8)
            self.symbols.append(Symbol(idx, pos, name, value, sectnum, aux))
            pos += 18 * (1 + aux)
            idx += 1 + aux
        self.symbol_by_name = {s.name: s for s in self.symbols}
        self.symbol_by_index = {s.index: s for s in self.symbols}

    def write(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.buf)

    def section(self, index: int) -> Section:
        return self.sections[index - 1]

    def symbol(self, name: str) -> Symbol:
        return self.symbol_by_name[name]

    def section_data(self, section_index: int) -> memoryview:
        sec = self.section(section_index)
        return memoryview(self.buf)[sec.raw_ptr : sec.raw_ptr + sec.raw_size]

    def _set_section_raw_size(self, sec: Section, size: int):
        struct.pack_into("<I", self.buf, sec.header_off + 16, size)

    def _set_section_raw_ptr(self, sec: Section, ptr: int):
        struct.pack_into("<I", self.buf, sec.header_off + 20, ptr)

    def _set_section_reloc_ptr(self, sec: Section, ptr: int):
        struct.pack_into("<I", self.buf, sec.header_off + 24, ptr)

    def _set_section_nreloc(self, sec: Section, nreloc: int):
        struct.pack_into("<H", self.buf, sec.header_off + 32, nreloc)

    def _set_symptr(self, ptr: int):
        struct.pack_into("<I", self.buf, 8, ptr)

    def _set_nsyms(self, nsyms: int):
        struct.pack_into("<I", self.buf, 12, nsyms)

    def _patch_section_aux_lengths(self, sec_index: int, delta_len: int):
        # COFF section symbols have an aux record immediately after the symbol:
        # length at +0, relocation count at +4. Link accepts section headers, but
        # updating aux keeps dumpbin/link diagnostics consistent.
        for sym in self.symbols:
            if sym.aux and sym.name == self.section(sec_index).name and sym.section == sec_index:
                aux_off = sym.off + 18
                old_len = struct.unpack_from("<I", self.buf, aux_off)[0]
                struct.pack_into("<I", self.buf, aux_off, old_len + delta_len)
                struct.pack_into("<H", self.buf, aux_off + 4, self.section(sec_index).nreloc)
                struct.pack_into("<H", self.buf, aux_off + 6, 0)

    def insert_section_bytes(self, sec_index: int, section_offset: int, payload: bytes):
        if not payload:
            return
        sec = self.section(sec_index)
        if section_offset < 0 or section_offset > sec.raw_size:
            raise ValueError("section_offset out of range")
        insert_at = sec.raw_ptr + section_offset
        delta = len(payload)
        self.buf[insert_at:insert_at] = payload

        # Update section headers.
        for s in self.sections:
            if s.index == sec_index:
                if s.raw_ptr and s.raw_ptr > insert_at:
                    s.raw_ptr += delta
                    self._set_section_raw_ptr(s, s.raw_ptr)
                if s.reloc_ptr and s.reloc_ptr >= insert_at:
                    s.reloc_ptr += delta
                    self._set_section_reloc_ptr(s, s.reloc_ptr)
                s.raw_size += delta
                self._set_section_raw_size(s, s.raw_size)
            else:
                if s.raw_ptr and s.raw_ptr >= insert_at:
                    s.raw_ptr += delta
                    self._set_section_raw_ptr(s, s.raw_ptr)
                if s.reloc_ptr and s.reloc_ptr >= insert_at:
                    s.reloc_ptr += delta
                    self._set_section_reloc_ptr(s, s.reloc_ptr)

        if self.symptr >= insert_at:
            self.symptr += delta
            self._set_symptr(self.symptr)
        self.strtab_ptr += delta

        # Shift symbol values that point after the inserted byte range in the grown section.
        for sym in self.symbols:
            if sym.off >= insert_at:
                sym.off += delta
            if sym.section == sec_index and sym.value >= section_offset:
                sym.value += delta
                struct.pack_into("<I", self.buf, sym.off + 8, sym.value)

        # Shift relocation virtual addresses inside the grown section, and shift
        # relocation records whose file offsets moved.
        for s in self.sections:
            p = s.reloc_ptr
            for _ in range(s.nreloc):
                if p >= insert_at:
                    pass
                if s.index == sec_index:
                    vaddr = struct.unpack_from("<I", self.buf, p)[0]
                    if vaddr >= section_offset:
                        struct.pack_into("<I", self.buf, p, vaddr + delta)
                p += 10

        self._parse()
        self._patch_section_aux_lengths(sec_index, delta)
        self._parse()

    def grow_bss_section(self, sec_index: int, section_offset: int, size: int):
        if size <= 0:
            return
        sec = self.section(sec_index)
        if sec.raw_ptr != 0:
            raise ValueError("grow_bss_section only applies to sections without raw data")
        if section_offset < 0 or section_offset > sec.raw_size:
            raise ValueError("section_offset out of range")
        sec.raw_size += size
        self._set_section_raw_size(sec, sec.raw_size)
        for sym in self.symbols:
            if sym.section == sec_index and sym.value >= section_offset:
                sym.value += size
                struct.pack_into("<I", self.buf, sym.off + 8, sym.value)
        self._parse()
        self._patch_section_aux_lengths(sec_index, size)
        self._parse()

    def set_u32_at_symbol_plus(self, sym_name: str, addend: int, value: int):
        sym = self.symbol(sym_name)
        sec = self.section(sym.section)
        struct.pack_into("<I", self.buf, sec.raw_ptr + sym.value + addend, value)

    def append_undefined_symbol(self, name: str) -> int:
        if name in self.symbol_by_name:
            return self.symbol_by_name[name].index

        old_strtab_ptr = self.symptr + self.nsyms * 18
        old_strtab_size = struct.unpack_from("<I", self.buf, old_strtab_ptr)[0]
        name_off = old_strtab_size
        new_strtab_size = old_strtab_size + len(name.encode("ascii")) + 1

        sym = bytearray(18)
        struct.pack_into("<II", sym, 0, 0, name_off)
        struct.pack_into("<IhHBB", sym, 8, 0, 0, 0, 2, 0)
        self.buf[old_strtab_ptr:old_strtab_ptr] = sym
        new_strtab_ptr = old_strtab_ptr + 18
        struct.pack_into("<I", self.buf, new_strtab_ptr, new_strtab_size)
        self.buf[new_strtab_ptr + old_strtab_size : new_strtab_ptr + old_strtab_size] = name.encode("ascii") + b"\0"
        self.nsyms += 1
        self._set_nsyms(self.nsyms)
        self.symptr = self.symptr
        self._parse()
        return self.symbol_by_name[name].index

    def append_relocation(self, sec_index: int, vaddr: int, symidx: int, rtype: int = IMAGE_REL_I386_DIR32):
        sec = self.section(sec_index)
        if sec.reloc_ptr == 0:
            insert_at = self.symptr
            sec.reloc_ptr = insert_at
            self._set_section_reloc_ptr(sec, sec.reloc_ptr)
        else:
            insert_at = sec.reloc_ptr + sec.nreloc * 10
        rec = struct.pack("<IIH", vaddr, symidx, rtype)
        self.buf[insert_at:insert_at] = rec
        delta = len(rec)
        sec.nreloc += 1
        self._set_section_nreloc(sec, sec.nreloc)

        for s in self.sections:
            if s.raw_ptr and s.raw_ptr >= insert_at:
                s.raw_ptr += delta
                self._set_section_raw_ptr(s, s.raw_ptr)
            if s.index != sec_index and s.reloc_ptr and s.reloc_ptr >= insert_at:
                s.reloc_ptr += delta
                self._set_section_reloc_ptr(s, s.reloc_ptr)

        if self.symptr >= insert_at:
            self.symptr += delta
            self._set_symptr(self.symptr)
        self.strtab_ptr += delta

        for sym in self.symbols:
            if sym.off >= insert_at:
                sym.off += delta

        self._parse()
        self._patch_section_aux_lengths(sec_index, 0)
        self._parse()

    def retarget_relocation(self, sec_index: int, vaddr: int, symidx: int, rtype: int | None = None):
        sec = self.section(sec_index)
        p = sec.reloc_ptr
        for _ in range(sec.nreloc):
            rec_vaddr = struct.unpack_from("<I", self.buf, p)[0]
            if rec_vaddr == vaddr:
                struct.pack_into("<I", self.buf, p + 4, symidx)
                if rtype is not None:
                    struct.pack_into("<H", self.buf, p + 8, rtype)
                self._parse()
                return
            p += 10
        raise ValueError(f"relocation not found for section {sec_index} vaddr {vaddr:#x}")
