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


def _obj(section_name: bytes, code: bytes, relocs=()):
    """Smallest COFF object that CoffObject will parse: one section, no syms."""
    nreloc = len(relocs)
    header = struct.pack("<HHIIIHH", 0x014C, 1, 0, 0, 0, 0, 0)
    sec_hdr_off = len(header)
    raw_ptr = sec_hdr_off + 40
    reloc_ptr = raw_ptr + len(code) if nreloc else 0
    name = section_name.ljust(8, b"\0")
    sec = name + struct.pack(
        "<IIIIIIHHI", 0, 0, len(code), raw_ptr, reloc_ptr, 0, nreloc, 0, 0x60000020
    )
    body = code + b"".join(struct.pack("<IIH", va, sym, typ) for va, sym, typ in relocs)
    buf = bytearray(header + sec + body)
    # symbol table pointer / count: none
    struct.pack_into("<I", buf, 8, len(buf))
    struct.pack_into("<I", buf, 12, 0)
    buf += struct.pack("<I", 4)  # empty string table
    path = pathlib.Path(_TMP.name) / f"probe{next(_SEQ)}.obj"
    path.write_bytes(bytes(buf))
    return CoffObject(path)


def _code_of(obj):
    sec = obj.section(1)
    return bytes(obj.buf[sec.raw_ptr:sec.raw_ptr + sec.raw_size])


class TestInsertKeepsBranchesAimed(unittest.TestCase):
    def test_rel32_forward_branch_is_widened_by_the_insert(self):
        # jne +0x10 ; 0x10 bytes of filler ; nop  -> target is the nop
        code = bytes((0x0F, 0x85, 0x10, 0x00, 0x00, 0x00)) + b"\x90" * 0x10 + b"\xCC"
        target_before = 6 + 0x10
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 10, b"\x90" * 4)
        rel = struct.unpack_from("<i", _code_of(obj), 2)[0]
        self.assertEqual(6 + rel, target_before + 4,
                         "a forward branch over the insert must gain the payload size")

    def test_rel8_backward_branch_is_widened_by_the_insert(self):
        # filler ; jmp back to offset 0
        code = b"\x90" * 0x10 + bytes((0xEB, 0xEE))
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 8, b"\x90" * 4)
        body = _code_of(obj)
        jmp_at = 0x10 + 4
        rel = struct.unpack_from("<b", body, jmp_at + 1)[0]
        self.assertEqual(jmp_at + 2 + rel, 0,
                         "a backward branch over the insert must still reach its target")

    def test_branch_aimed_at_the_insertion_point_enters_the_new_code(self):
        # This is how the hooks are threaded in: the jump is meant to land on
        # the payload, not to follow the old code that moved out of the way.
        code = bytes((0xEB, 0x0E)) + b"\x90" * 0x0E + b"\xCC"
        obj = _obj(b".text$mn", code)
        obj.insert_section_bytes(1, 0x10, b"\x90" * 4)
        rel = struct.unpack_from("<b", _code_of(obj), 1)[0]
        self.assertEqual(2 + rel, 0x10, "the branch should still land on the payload")

    def test_relocated_displacements_are_left_to_the_linker(self):
        # call rel32 with a relocation over its displacement: a zero placeholder
        # the linker fills, never something to re-encode here.
        code = bytes((0xE8, 0x00, 0x00, 0x00, 0x00)) + b"\x90" * 0x20
        obj = _obj(b".text$mn", code, relocs=[(1, 0, 0x0014)])
        obj.insert_section_bytes(1, 0x10, b"\x90" * 4)
        rel = struct.unpack_from("<i", _code_of(obj), 1)[0]
        self.assertEqual(rel, 0, "a relocated displacement must stay untouched")

    def test_data_sections_are_left_alone(self):
        # Byte patterns in data must never be mistaken for branches.
        code = bytes((0x0F, 0x85, 0x10, 0x00, 0x00, 0x00)) + b"\x90" * 0x10
        obj = _obj(b".data", code)
        obj.insert_section_bytes(1, 10, b"\x00" * 4)
        rel = struct.unpack_from("<i", _code_of(obj), 2)[0]
        self.assertEqual(rel, 0x10, "data bytes must not be re-encoded as branches")

    def test_insert_that_splits_an_instruction_is_refused(self):
        code = bytes((0x0F, 0x85, 0x10, 0x00, 0x00, 0x00)) + b"\x90" * 0x10
        obj = _obj(b".text$mn", code)
        with self.assertRaises(ValueError):
            obj.insert_section_bytes(1, 3, b"\x90" * 4)

    def test_rel8_pushed_out_of_range_is_refused_rather_than_truncated(self):
        code = bytes((0xEB, 0x7E)) + b"\x90" * 0x80
        obj = _obj(b".text$mn", code)
        with self.assertRaises(ValueError):
            obj.insert_section_bytes(1, 0x40, b"\x90" * 0x20)


if __name__ == "__main__":
    unittest.main()
