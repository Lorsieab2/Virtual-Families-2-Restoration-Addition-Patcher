from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import struct
import sys


IMAGE_REL_I386_DIR32 = 0x0006
IMAGE_SYM_CLASS_EXTERNAL = 2
IMAGE_SYM_CLASS_STATIC = 3


def _relative_branches(code: bytes):
    """Yield (ins_offset, ins_len, disp_offset, disp_size, target) for every
    instruction in ``code`` that jumps or calls a *relative* destination.

    These displacements are resolved by the compiler inside a single section,
    so they carry no relocation record. Nothing else in this file knows about
    them, which is why growing a code section used to silently break every
    branch that spanned the insertion point.
    """
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    from capstone.x86 import X86_OP_IMM

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    for ins in md.disasm(code, 0):
        if not ins.operands:
            continue
        op = ins.operands[0]
        if op.type != X86_OP_IMM:
            continue
        opc = ins.bytes[0]
        if opc in (0xE8, 0xE9):                      # call rel32 / jmp rel32
            disp_off, disp_size = 1, 4
        elif opc == 0x0F and 0x80 <= ins.bytes[1] <= 0x8F:   # jcc rel32
            disp_off, disp_size = 2, 4
        elif 0x70 <= opc <= 0x7F or opc in (0xEB, 0xE0, 0xE1, 0xE2, 0xE3):
            disp_off, disp_size = 1, 1               # jcc/jmp/loop/jecxz rel8
        else:
            continue
        yield ins.address, ins.size, disp_off, disp_size, op.imm


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

    def set_symbol_storage_class(self, name: str, storage_class: int):
        sym = self.symbol(name)
        struct.pack_into("<B", self.buf, sym.off + 16, storage_class)
        self._parse()

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

    def insert_section_bytes(self, sec_index: int, section_offset: int, payload: bytes,
                             fix_relative_branches: bool = True):
        if not payload:
            return
        sec = self.section(sec_index)
        if section_offset < 0 or section_offset > sec.raw_size:
            raise ValueError("section_offset out of range")
        insert_at = sec.raw_ptr + section_offset
        delta = len(payload)
        code_before = None
        relocated_before = None
        if (fix_relative_branches and sec.name.startswith(".text")
                and sec.raw_ptr and section_offset < sec.raw_size):
            code_before = bytes(self.buf[sec.raw_ptr:sec.raw_ptr + sec.raw_size])
            relocated_before = set()
            reloc_at = sec.reloc_ptr
            for _ in range(sec.nreloc):
                relocated_before.add(struct.unpack_from("<I", self.buf, reloc_at)[0])
                reloc_at += 10
        self.buf[insert_at:insert_at] = payload
        if code_before is not None:
            self._retarget_relative_branches(
                sec, section_offset, delta, code_before, relocated_before
            )

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

    def _retarget_relative_branches(self, sec, section_offset: int, delta: int,
                                    code_before: bytes, relocated: set):
        """Keep intra-section jumps pointing at the same instructions after a grow.

        Relative branches are not relocations, so inserting bytes in the middle
        of a code section leaves every displacement that spans the insertion
        point short by ``delta``. A branch then lands mid-instruction, which
        desynchronises the decoder and corrupts the frame -- the cause of the
        VF2 startup crash traced to VillagerAI.obj, where CVillagerAI's
        early-out jumped one byte into the tail of a `jne`.

        The old offsets map onto the new ones by shifting everything at or
        after the insertion point, so each branch is simply re-encoded from the
        mapped source and target rather than guessed at.
        """
        def moved_position(offset: int) -> int:
            return offset + delta if offset >= section_offset else offset

        def moved_target(offset: int) -> int:
            # A branch aimed exactly at the insertion point is entering the
            # bytes being inserted, which is how these hooks are threaded in;
            # only destinations past it are old code that has shifted.
            return offset + delta if offset > section_offset else offset

        # Displacements that carry a relocation are filled in by the linker,
        # not by us: they sit in the object as zero placeholders and must be
        # left exactly as they are. ``relocated`` was collected before the
        # insert, so its offsets line up with ``code_before``.
        for ins_off, ins_len, disp_off, disp_size, target in _relative_branches(code_before):
            if ins_off + disp_off in relocated:
                continue
            if ins_off < section_offset < ins_off + ins_len:
                raise ValueError(
                    f"insert at {section_offset:#x} splits the instruction at "
                    f"{ins_off:#x} in {sec.name}"
                )
            new_end = moved_position(ins_off + ins_len)
            new_disp = moved_target(target) - new_end
            old_disp = target - (ins_off + ins_len)
            if new_disp == old_disp:
                continue
            if disp_size == 1 and not (-128 <= new_disp <= 127):
                raise ValueError(
                    f"growing {sec.name} by {delta} pushes the rel8 branch at "
                    f"{ins_off:#x} out of range ({new_disp}); it needs a rel32 form"
                )
            if os.environ.get("VF2_TRACE_BRANCH_FIX"):
                print(f"[branchfix] {sec.name} ins@{ins_off:#x} disp {old_disp:#x} -> "
                      f"{new_disp:#x} (target {target:#x})", file=sys.stderr)
            fmt = "<b" if disp_size == 1 else "<i"
            struct.pack_into(
                fmt, self.buf, sec.raw_ptr + moved_position(ins_off) + disp_off, new_disp
            )

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
