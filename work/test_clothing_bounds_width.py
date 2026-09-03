#!/usr/bin/env python3
"""The Clothing and Hairstyles bounds check must survive passing 128 rows.

CInventoryManager::GetCategoryItem guards that category with

    0x313: 83 FE 05        cmp esi,5
    0x316: 0F 87 rel32     ja  $LN55

`83 /7 ib` is CMP r/m32, imm8 with the immediate SIGN-EXTENDED to 32 bits,
while the JA that consumes the flags is unsigned. So writing a max index above
127 into that byte does not widen the guard -- it inverts it. A max index of
213 becomes 0xD5, sign-extends to 0xFFFFFFD5, and the JA then admits every
realistic index, letting the store read past the end of gClothingList.

With the outfit rows alone the category holds 114 entries (max index 113) and
still fits, so this never bit. Adding the 100 hairstyle rows takes it to 214,
which does not, and the patcher must emit the 6-byte `81 FE id` form instead.
"""
import struct
import unittest

import patch_mobile_furniture_pack as patcher


STOCK_BOUNDS = bytes.fromhex("83fe05")
STOCK_JA = bytes.fromhex("0f8720010000")


def _widened(max_index, ja_rel32):
    return (
        b"\x81\xfe" + struct.pack("<I", max_index)
        + b"\x0f\x87" + struct.pack("<i", ja_rel32)
    )


class TestClothingBoundsWidth(unittest.TestCase):
    def test_the_category_now_exceeds_the_imm8_form(self):
        rows = 6 + patcher.OUTFIT_STORE_ENTRY_COUNT + patcher.HEAD_STORE_ENTRY_COUNT
        self.assertGreater(
            rows - 1, 127,
            "if the max index still fits in a sign-extended imm8 this guard "
            "does not need widening -- and this test is no longer meaningful",
        )

    def test_a_sign_extended_imm8_would_disable_the_guard(self):
        # This is the defect the widening exists to avoid, stated as arithmetic.
        max_index = 6 + patcher.OUTFIT_STORE_ENTRY_COUNT + patcher.HEAD_STORE_ENTRY_COUNT - 1
        byte = max_index & 0xFF
        sign_extended = byte - 0x100 if byte > 0x7F else byte
        self.assertNotEqual(
            sign_extended & 0xFFFFFFFF, max_index,
            "the imm8 form would have compared against the wrong value",
        )
        self.assertGreater(
            sign_extended & 0xFFFFFFFF, 0x7FFFFFFF,
            "the sign-extended immediate is huge, so 'ja' would admit "
            "essentially every index",
        )

    def test_the_widened_form_compares_the_real_value(self):
        max_index = 213
        ja_rel32 = struct.unpack_from("<i", STOCK_JA, 2)[0]
        widened = _widened(max_index, ja_rel32)
        self.assertEqual(widened[:2], b"\x81\xfe", "must be cmp esi, imm32")
        self.assertEqual(struct.unpack_from("<I", widened, 2)[0], max_index)
        self.assertEqual(widened[6:8], b"\x0f\x87", "must still be a near ja")
        self.assertEqual(struct.unpack_from("<i", widened, 8)[0], ja_rel32,
                         "the branch keeps its original displacement")

    def test_the_widened_form_is_three_bytes_longer(self):
        # Those three bytes are inserted, which moves every following
        # instruction -- so the insert must go through the code-section grower
        # that re-aims intra-section branches, not a plain overwrite.
        widened = _widened(213, struct.unpack_from("<i", STOCK_JA, 2)[0])
        self.assertEqual(len(widened) - len(STOCK_BOUNDS + STOCK_JA), 3)

    def test_the_gap_is_inserted_before_the_widened_bytes_are_written(self):
        # insert_section_bytes decodes the section and requires the insertion
        # point to be an instruction boundary. Writing the 12-byte pair into
        # the 9 original bytes first would leave a half-formed "ja" straddling
        # that point -- its last three bytes still belonging to the following
        # instruction -- and the decode would reject it, stopping every build.
        path = patcher.ROOT / "work" / "patch_mobile_furniture_pack.py"
        src = path.read_text(encoding="utf-8")
        insert_at = src.index("clothing_bounds_off + 9, bytes([0x90])")
        write_at = src.index("clothing_bounds_raw + 12] = widened")
        self.assertLess(
            insert_at, write_at,
            "the three-byte gap must be inserted while the original cmp/ja "
            "pair is still a valid instruction sequence",
        )

    def test_the_grower_re_aims_branches_across_the_insertion(self):
        # A branch that jumps over the insertion point must still land on the
        # same instruction afterwards.
        from coff_patch import _decode_code_section

        code = bytearray()
        code += b"\x0f\x87" + struct.pack("<i", 9)   # ja +9 -> lands past the gap
        code += b"\x90" * 9
        code += b"\xc3"
        starts, branches, _covered = _decode_code_section(bytes(code))
        self.assertTrue(branches, "the ja should have been decoded as a branch")
        addr, size, disp_off, disp_size, target = branches[0]
        self.assertEqual(addr, 0)
        self.assertEqual(disp_size, 4)
        self.assertEqual(target, 15, "ja at 0 of size 6 with disp 9 targets 15")


if __name__ == "__main__":
    unittest.main()
