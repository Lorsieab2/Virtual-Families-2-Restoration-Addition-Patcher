"""Growing a code section must not break the branches that span the insert.

Relative jumps and calls inside one section carry no relocation record: the
compiler resolves them when it emits the object. Inserting bytes in the middle
of `.text` therefore leaves every displacement that spans the insertion point
short by the size of the payload, and the branch lands mid-instruction.

That is not hypothetical. It shipped: CVillagerAI's early-out in
VillagerAI.obj jumped to the tail byte of a `jne`, the decoder desynchronised
into `add al, 0x85`, the epilogue popped the wrong slots, and the caller
resumed with a null `this` and faulted on `cmp dword ptr [esi], 0` -- the
Virtual Families 2 startup crash.
"""
import pathlib
import struct
import tempfile
import unittest

from coff_patch import CoffObject

_TMP = tempfile.TemporaryDirectory()
_SEQ = iter(range(1 << 20))

NOP = b"\x90"
INT3 = b"\xCC"


def _obj(section_name: bytes, code: bytes, relocs=()):
    """Smallest COFF object that CoffObject will parse: one section, no syms."""
    nreloc = len(relocs)
    header = struct.pack("<HHIIIHH", 0x014C, 1, 0, 0, 0, 0, 0)
    raw_ptr = len(header) + 40
    reloc_ptr = raw_ptr + len(code) if nreloc else 0
    name = section_name.ljust(8, b"\0")
    sec = name + struct.pack(
        "<IIIIIIHHI", 0, 0, len(code), raw_ptr, reloc_ptr, 0, nreloc, 0, 0x60000020
    )
    body = code + b"".join(struct.pack("<IIH", va, sym, typ) for va, sym, typ in relocs)
    buf = bytearray(header + sec + body)
    struct.pack_into("<I", buf, 8, len(buf))   # symbol table pointer
    struct.pack_into("<I", buf, 12, 0)         # no symbols
    buf += struct.pack("<I", 4)                # empty string table
    path = pathlib.Path(_TMP.name) / f"probe{next(_SEQ)}.obj"
    path.write_bytes(bytes(buf))
    return CoffObject(path)


def _code_of(obj):
    sec = obj.section(1)
    return bytes(obj.buf[sec.raw_ptr:sec.raw_ptr + sec.raw_size])


class TestInsertKeepsBranchesAimed(unittest.TestCase):
    def test_rel32_forward_branch_is_widened_by_the_insert(self):
        code = bytes((0x0F, 0x85, 0x10, 0x00, 0x00, 0x00)) + NOP * 0x10 + INT3
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 10, NOP * 4)
        rel = struct.unpack_from("<i", _code_of(obj), 2)[0]
        self.assertEqual(6 + rel, 6 + 0x10 + 4,
                         "a forward branch over the insert must gain the payload size")

    def test_rel8_backward_branch_is_widened_by_the_insert(self):
        code = NOP * 0x10 + bytes((0xEB, 0xEE))     # jmp back to offset 0
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 8, NOP * 4)
        jmp_at = 0x10 + 4
        rel = struct.unpack_from("<b", _code_of(obj), jmp_at + 1)[0]
        self.assertEqual(jmp_at + 2 + rel, 0,
                         "a backward branch over the insert must still reach its target")

    def test_branch_ending_exactly_at_the_insert_still_reaches_its_target(self):
        # The instruction sits entirely before the payload, so its end must not
        # be shifted. If it were, the target's shift would cancel out and the
        # branch would land inside the inserted bytes.
        code = bytes((0x0F, 0x85, 0x10, 0x00, 0x00, 0x00)) + NOP * 0x20
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 6, NOP * 4)     # immediately after the jne
        rel = struct.unpack_from("<i", _code_of(obj), 2)[0]
        self.assertEqual(6 + rel, 6 + 0x10 + 4,
                         "the branch must follow its target past the payload")

    def test_branch_aimed_at_the_insertion_point_enters_the_new_code(self):
        # This is how the hooks are threaded in: the jump is meant to land on
        # the payload, not to follow the old code that moved out of the way.
        code = bytes((0xEB, 0x0E)) + NOP * 0x0E + INT3
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 0x10, NOP * 4)
        rel = struct.unpack_from("<b", _code_of(obj), 1)[0]
        self.assertEqual(2 + rel, 0x10, "the branch should still land on the payload")

    def test_prefixed_branch_is_retargeted(self):
        # A legally prefixed branch is still a branch. Reading the opcode from
        # byte zero would see the prefix and skip it.
        code = bytes((0x2E, 0x0F, 0x85, 0x10, 0x00, 0x00, 0x00)) + NOP * 0x20
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 0x10, NOP * 4)
        rel = struct.unpack_from("<i", _code_of(obj), 3)[0]
        self.assertEqual(7 + rel, 7 + 0x10 + 4,
                         "a cs-prefixed jne must be retargeted like any other")

    def test_operand_size_prefixed_branch_uses_its_own_displacement_width(self):
        code = bytes((0x66, 0xE9, 0x20, 0x00)) + NOP * 0x30
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 0x10, NOP * 4)
        rel = struct.unpack_from("<h", _code_of(obj), 2)[0]
        self.assertEqual(4 + rel, 4 + 0x20 + 4,
                         "the 16-bit form must be widened in its own width")

    def test_relocated_displacements_are_left_to_the_linker(self):
        # call rel32 with a relocation over its displacement: a zero placeholder
        # the linker fills, never something to re-encode here.
        code = bytes((0xE8, 0x00, 0x00, 0x00, 0x00)) + NOP * 0x20
        obj = _obj(b".text$mn", code, relocs=[(1, 0, 0x0014)])
        obj.insert_section_bytes(1, 0x10, NOP * 4)
        rel = struct.unpack_from("<i", _code_of(obj), 1)[0]
        self.assertEqual(rel, 0, "a relocated displacement must stay untouched")

    def test_data_sections_are_left_alone(self):
        # Byte patterns in data must never be mistaken for branches.
        code = bytes((0x0F, 0x85, 0x10, 0x00, 0x00, 0x00)) + NOP * 0x10
        obj = _obj(b".data", code)
        obj.insert_section_bytes(1, 10, b"\x00" * 4)
        rel = struct.unpack_from("<i", _code_of(obj), 2)[0]
        self.assertEqual(rel, 0x10, "data bytes must not be re-encoded as branches")

    def test_split_of_a_branch_is_refused(self):
        code = bytes((0x0F, 0x85, 0x10, 0x00, 0x00, 0x00)) + NOP * 0x10
        obj = _obj(b".text$mn", code)
        with self.assertRaises(ValueError):
            obj.insert_section_bytes(1, 3, NOP * 4)

    def test_split_of_an_ordinary_instruction_is_refused(self):
        # Not a branch: a 5-byte mov. Splitting it produces invalid code just
        # as surely as splitting a jump.
        code = bytes((0xB8, 0x11, 0x22, 0x33, 0x44)) + NOP * 0x10
        obj = _obj(b".text$mn", code)
        with self.assertRaises(ValueError):
            obj.insert_section_bytes(1, 2, NOP * 4)

    def test_rel8_pushed_out_of_range_is_refused_rather_than_truncated(self):
        code = bytes((0xEB, 0x7E)) + NOP * 0x80
        obj = _obj(b".text$mn", code)
        with self.assertRaises(ValueError):
            obj.insert_section_bytes(1, 0x40, NOP * 0x20)

    def test_a_single_undecodable_trailing_byte_is_tolerated(self):
        # The shortest relative branch is two bytes, so one trailing byte
        # provably cannot hide one. InventoryManager.obj ends on exactly this.
        code = bytes((0xEB, 0x10)) + NOP * 0x20 + bytes((0x03,))
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 0x10, NOP * 4)
        rel = struct.unpack_from("<b", _code_of(obj), 1)[0]
        self.assertEqual(2 + rel, 2 + 0x10 + 4)

    def test_a_two_byte_undecodable_tail_is_refused(self):
        # Two bytes is enough for a rel8 branch, so it can no longer be
        # dismissed as padding.
        code = NOP * 0x20 + bytes((0xFF, 0xFF))
        obj = _obj(b".text$mn", code)
        with self.assertRaises(ValueError):
            obj.insert_section_bytes(1, 0x10, NOP * 4)

    def test_undecodable_section_is_refused_rather_than_half_checked(self):
        # If the decoder cannot account for every byte it cannot promise it saw
        # every branch, so growing the section is refused outright.
        code = NOP * 4 + b"\xFF\xFF\xFF\xFF" + NOP * 4
        obj = _obj(b".text$mn", code)
        with self.assertRaises(ValueError):
            obj.insert_section_bytes(1, 4, NOP * 4)


if __name__ == "__main__":
    unittest.main()
