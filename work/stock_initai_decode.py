"""Decode stock CVillager::InitAI candidate field writes from Villager.obj.

InitAI first writes default values into every 0xD0-byte candidate record
(base CVillager+0x6BB8), then dispatches on the behaviour id through a
two-level jump table:

    movzx eax, byte ptr $LN205[eax]      ; id - 2 -> case index
    jmp   dword ptr $LN249[eax*4]        ; case index -> case code

Each case writes fields of its own record as [esi+eax+(0x6BB8+field)] (or
with another index register) and jumps to the shared tail. An id whose case
is the SHARED DEFAULT target writes nothing, so it keeps the defaults.

The object file is used, not a shipped executable, so this works from the
repository's own build inputs (work/desktop_obj_files).
"""
import struct

import capstone
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

from coff_patch import CoffObject

CANDIDATE_BASE = 0x6BB8
CANDIDATE_SIZE = 0xD0
CANDIDATE_COUNT = 0x19B


def _reloc_map(obj, sec):
    relocs = {}
    for i in range(sec.nreloc):
        vaddr, symidx, rtype = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + i * 10)
        relocs[vaddr] = obj.symbol_by_index[symidx]
    return relocs


def decode(villager_obj_path):
    """Return (default_case_offset, {behavior_id: {field: value}}, {id: case_offset})."""
    obj = CoffObject(villager_obj_path)
    init = obj.symbol("?InitAI@CVillager@@QAEXXZ")
    sec = obj.section(init.section)
    code = bytes(obj.buf[sec.raw_ptr:sec.raw_ptr + sec.raw_size])
    relocs = _reloc_map(obj, sec)

    def resolved(field_offset):
        # A DIR32 slot: the stored value is the addend to the symbol's value.
        sym = relocs[field_offset]
        addend = struct.unpack_from("<I", code, field_offset)[0]
        assert sym.section == init.section, sym.name
        return sym.value + addend

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    table1 = table2 = None
    for ins in md.disasm(code[init.value:init.value + 0x400], init.value):
        if ins.mnemonic == "movzx" and table1 is None and ins.operands[1].type == X86_OP_MEM:
            table1 = resolved(ins.address + ins.size - 4)
        if ins.mnemonic == "jmp" and ins.operands[0].type == X86_OP_MEM:
            table2 = resolved(ins.address + ins.size - 4)
            break
    assert table1 is not None and table2 is not None, "InitAI switch not found"

    def case_offset(bid):
        index = code[table1 + bid - 2]
        return resolved(table2 + 4 * index)

    # The byte table covers ids 2..(2 + its length - 1); ids outside it never
    # reach a case (the switch bound check sends them to the tail).
    last = 2 + (sec.raw_size - table1) - 1
    cases = {bid: case_offset(bid) for bid in range(2, min(CANDIDATE_COUNT, last + 1))}
    counts = {}
    for off in cases.values():
        counts[off] = counts.get(off, 0) + 1
    default = max(counts, key=counts.get)

    fields = {}
    for bid, off in cases.items():
        writes = {}
        if off != default:
            for ins in md.disasm(code[off:off + 0x300], off):
                if ins.mnemonic == "mov" and ins.operands[0].type == X86_OP_MEM \
                        and ins.operands[1].type == X86_OP_IMM:
                    disp = ins.operands[0].mem.disp
                    if CANDIDATE_BASE <= disp < CANDIDATE_BASE + CANDIDATE_SIZE:
                        writes[disp - CANDIDATE_BASE] = ins.operands[1].imm & 0xFFFFFFFF
                if ins.mnemonic in ("jmp", "ret"):
                    break
        fields[bid] = writes
    return default, fields, cases
