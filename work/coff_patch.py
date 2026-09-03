from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import struct
import sys


IMAGE_REL_I386_DIR32 = 0x0006
IMAGE_SYM_CLASS_EXTERNAL = 2
IMAGE_SYM_CLASS_STATIC = 3


def _decode_code_section(code: bytes):
    """Decode a code section into (instruction starts, relative branches, bytes covered).

    Relative displacements are resolved by the compiler inside a single
    section, so they carry no relocation record. Nothing else in this file
    knows about them, which is why growing a code section used to silently
    break every branch that spanned the insertion point.

    Branches are identified by Capstone's jump/call groups and an immediate
    operand rather than by opcode byte, so a legally prefixed branch is not
    missed, and the displacement field is taken from the instruction encoding
    so a prefix or a 16-bit form does not shift it out from under us. The far
    forms (`ljmp` / `lcall`) take an absolute destination and are skipped.
    """
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_GRP_CALL, CS_GRP_JUMP
        from capstone.x86 import X86_OP_IMM
    except ImportError as exc:  # pragma: no cover - environment problem
        raise ImportError(
            "capstone is required to grow a code section safely: the relative "
            "branches spanning the insertion point have to be decoded before "
            "they can be re-encoded. Install it with "
            "`python -m pip install -r requirements-build.txt`."
        ) from exc

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    starts = set()
    branches = []
    covered = 0
    for ins in md.disasm(code, 0):
        starts.add(ins.address)
        covered = ins.address + ins.size
        if not ins.operands or ins.mnemonic in ("ljmp", "lcall"):
            continue
        op = ins.operands[0]
        if op.type != X86_OP_IMM:
            continue
        if not (ins.group(CS_GRP_JUMP) or ins.group(CS_GRP_CALL)):
            continue
        disp_off = ins.encoding.imm_offset
        disp_size = ins.encoding.imm_size
        if not disp_off or disp_size not in (1, 2, 4):
            continue
        branches.append((ins.address, ins.size, disp_off, disp_size, op.imm))
    return starts, branches, covered


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

        Inserting bytes in the middle of a code section leaves every relative
        displacement that spans the insertion point short by ``delta``, so the
        branch lands mid-instruction. That is the VF2 startup crash: CVillagerAI's
        early-out jumped one byte into the tail of a `jne`, the decoder
        desynchronised, and the caller resumed with a null `this`.

        Old offsets map onto new ones by shifting everything at or after the
        insertion point, so each branch is re-encoded from the mapped source and
        target rather than guessed at.
        """
        starts, branches, covered = _decode_code_section(code_before)
        # The decoder stops at the first byte it cannot read, so anything past
        # `covered` is unexamined and might hide a branch we would fail to
        # retarget. Tolerating a tail "because it looks like padding" would be
        # guessing, so the only tail accepted is one too small to hold a
        # branch at all: the shortest relative branch is two bytes, so a single
        # trailing byte provably cannot be one. InventoryManager.obj ends on
        # exactly that -- a lone 0x03 after its last instruction. Anything
        # longer, or anything before the insertion point, is refused.
        tail = len(code_before) - covered
        if tail and (covered < section_offset or tail >= 2):
            raise ValueError(
                f"only decoded {covered:#x} of {len(code_before):#x} bytes of "
                f"{sec.name}; refusing to grow a section whose branches cannot "
                "all be accounted for"
            )
        if section_offset not in starts and section_offset != len(code_before):
            raise ValueError(
                f"insert at {section_offset:#x} is not an instruction boundary "
                f"in {sec.name}"
            )

        def moved_position(offset: int) -> int:
            return offset + delta if offset >= section_offset else offset

        def moved_target(offset: int) -> int:
            # A branch aimed exactly at the insertion point is entering the
            # bytes being inserted, which is how these hooks are threaded in;
            # only destinations past it are old code that has shifted.
            return offset + delta if offset > section_offset else offset

        limits = {1: (-128, 127), 2: (-32768, 32767), 4: (-(1 << 31), (1 << 31) - 1)}
        formats = {1: "<b", 2: "<h", 4: "<i"}

        for ins_off, ins_len, disp_off, disp_size, target in branches:
            if ins_off + disp_off in relocated:
                # Filled in by the linker: a zero placeholder, not ours to touch.
                continue
            # The end of an instruction follows its own start. Mapping the end
            # offset independently would shift a branch that ends exactly at the
            # insertion point, cancelling out the target's shift and dropping it
            # into the payload.
            new_end = moved_position(ins_off) + ins_len
            new_disp = moved_target(target) - new_end
            if new_disp == target - (ins_off + ins_len):
                continue
            low, high = limits[disp_size]
            if not low <= new_disp <= high:
                raise ValueError(
                    f"growing {sec.name} by {delta} pushes the {disp_size * 8}-bit "
                    f"branch at {ins_off:#x} out of range ({new_disp}); it needs a "
                    "wider form"
                )
            if os.environ.get("VF2_TRACE_BRANCH_FIX"):
                print(f"[branchfix] {sec.name} ins@{ins_off:#x} -> {new_disp:#x} "
                      f"(target {target:#x})", file=sys.stderr)
            struct.pack_into(
                formats[disp_size], self.buf,
                sec.raw_ptr + moved_position(ins_off) + disp_off, new_disp,
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
