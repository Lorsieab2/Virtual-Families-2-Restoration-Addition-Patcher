"""The career-room goals come back on load and after Reset Achievements.

Owner report: "Office of the Future" did not autocomplete with every career
upgrade owned.

MECHANISM, decoded from the stock objects and pinned below:

  * achievement 0x37 ("Office of the future", name string 0x2FC, target 10)
    is RECOMPUTED, not counted. CTech::Level(1) counts HaveUpgrade over
    items 0xEB..0xF5, calls ResetSingleAchievementProgress(0x37), then
    IncrementProgress(0x37, min(count, 10)). Kitchen (0, items 0xF6..0xFF,
    goal 0x36) and workshop (2, 0x100..0x109, goal 0x38) work the same way.
  * Level(1) runs on an office upgrade purchase and otherwise only from
    villager code that concerns an office career. Nothing runs it on load.
  * The patcher's Reset Achievements cheat (0x124) calls
    Achievement.Reset() while the upgrades stay owned -- a state the stock
    game cannot reach -- so 0x37 stays at zero until an office purchase
    that can no longer happen.

FIX: the CTech::LoadState call inside theGameState::Load is retargeted to a
wrapper that runs the native load and then Tech.Level(0..2) -- the same
relocation-only shape as the pet and achiever load hooks -- and the 0x124
handler calls the same recompute after Achievement.Reset(). Both primitives
are no-ops on a completed record, so completed goals are untouched.
"""
import pathlib
import re
import shutil
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402
from coff_patch import CoffObject  # noqa: E402
IMAGE_REL_I386_REL32 = patcher.IMAGE_REL_I386_REL32

HELPER = "@VF2TechLoadStateAndReconcile@12"
NATIVE = "?LoadState@CTech@@QAE?B_NABUSSaveState@1@@Z"
LOAD = "?Load@theGameState@@UAE_NH@Z"


def _source():
    return GEN.read_text(encoding="utf-8")


def _strip_comments(text):
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        out.append(line.split("//")[0] if "//" in line else line)
    return "\n".join(out)


def _function(src, signature_start):
    i = -1
    while True:
        i = src.index(signature_start, i + 1)
        close = src.index(")", i)
        if src.startswith("\n{", close + 1) or src.startswith(" {", close + 1):
            end = src.index("\n}\n", close)
            return src[i:end]


def _reloc_target(obj, sec, vaddr):
    for index in range(sec.nreloc):
        v, symbol_index, rtype = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + index * 10)
        if v == vaddr:
            return obj.symbol_by_index[symbol_index].name, rtype
    return None


class GroundTruth(unittest.TestCase):
    """Pinned to the stock objects so the model is never re-derived."""

    def setUp(self):
        for name in ("Tech.obj", "theGameState.obj", "Achievement.obj"):
            if not (patcher.SRC_OBJS / name).is_file():
                self.skipTest("missing build input %s" % name)

    def _body(self, obj_name, symbol):
        obj = CoffObject(patcher.SRC_OBJS / obj_name)
        s = obj.symbol(symbol)
        sec = obj.section(s.section)
        return bytes(obj.buf[sec.raw_ptr + s.value: sec.raw_ptr + sec.raw_size])

    def test_level_one_rebuilds_the_office_goal_from_items_eb_to_f5(self):
        body = self._body("Tech.obj", "?Level@CTech@@QBEHW4ETech@@@Z")
        for item in range(0xEB, 0xF6):
            self.assertIn(b"\x68" + struct.pack("<I", item), body,
                          "Level no longer checks HaveUpgrade(%#x)" % item)
        self.assertIn(b"\xBB\x37\x00\x00\x00", body, "mov ebx,37h -- the office goal id")
        self.assertIn(b"\xBB\x36\x00\x00\x00", body, "mov ebx,36h -- the kitchen goal id")
        self.assertIn(b"\xBB\x38\x00\x00\x00", body, "mov ebx,38h -- the workshop goal id")
        self.assertIn(b"\xBF\x0A\x00\x00\x00", body, "mov edi,0Ah -- the cap of ten")

    def test_the_primitives_skip_a_completed_record(self):
        """cmp byte ptr [rec],0 / jne skip -- both routines bail when the
        complete flag is set, which is what makes the recompute safe."""
        inc = self._body("Achievement.obj", "?IncrementProgress@CAchievement@@QAEXW4EAchievement@@H@Z")
        rst = self._body("Achievement.obj", "?ResetSingleAchievementProgress@CAchievement@@QAEXW4EAchievement@@@Z")
        self.assertIn(b"\x80\x3C\x86\x00", inc[:0x14], "IncrementProgress no longer tests the complete flag first")
        self.assertIn(b"\x80\x3C\x81\x00", rst[:0x14], "ResetSingleAchievementProgress no longer tests the complete flag first")

    def test_the_load_site_is_where_the_generator_expects(self):
        obj = CoffObject(patcher.SRC_OBJS / "theGameState.obj")
        load = obj.symbol(LOAD)
        sec = obj.section(load.section)
        raw = sec.raw_ptr + load.value
        self.assertEqual(bytes(obj.buf[raw + 0x205: raw + 0x20A]), b"\xE8\0\0\0\0")
        self.assertEqual(_reloc_target(obj, sec, load.value + 0x206), (NATIVE, IMAGE_REL_I386_REL32))
        # Ownership and the achievement records are loaded BEFORE this site.
        inv = _reloc_target(obj, sec, load.value + 0x1BB)
        ach = _reloc_target(obj, sec, load.value + 0x134)
        self.assertEqual(inv[0], "?LoadState@CInventoryManager@@QAE_NABUSSaveState@1@@Z")
        self.assertEqual(ach[0], "?LoadState@CAchievement@@QAE?B_NAAUSSaveState@1@@Z")


class TheSource(unittest.TestCase):
    def test_ctech_is_declared_with_the_native_signatures(self):
        src = _strip_comments(_source())
        self.assertIn("enum ETech {\n    eTechKitchen = 0,\n    eTechOffice = 1,\n    eTechWorkshop = 2\n};", src)
        self.assertIn("class CTech {\npublic:\n    struct SSaveState;\n    int Level(ETech tech) const;\n    bool const LoadState(SSaveState const &state);\n};", src)
        self.assertIn("extern CTech Tech;", src)

    def test_the_recompute_covers_all_three_career_rooms(self):
        src = _strip_comments(_source())
        f = _function(src, "static void VF2ReconcileCareerRoomGoals()")
        for tech in ("eTechKitchen", "eTechOffice", "eTechWorkshop"):
            self.assertIn("Tech.Level(%s);" % tech, f, "%s is not recomputed" % tech)

    def test_the_load_wrapper_reconciles_only_after_a_successful_load(self):
        src = _strip_comments(_source())
        f = _function(src, 'extern "C" bool __fastcall VF2TechLoadStateAndReconcile(')
        self.assertIn("bool loaded = tech->LoadState(state);", f)
        self.assertIn("if (loaded) VF2ReconcileCareerRoomGoals();", f)
        self.assertIn("return loaded;", f)
        self.assertLess(f.index("tech->LoadState(state)"), f.index("VF2ReconcileCareerRoomGoals()"),
                        "the goals are recomputed before the save's tech state is loaded")

    def test_the_reset_cheat_recomputes_after_the_wipe(self):
        src = _strip_comments(_source())
        i = src.index("    case 0x124:")
        block = src[i:src.index("    case 0x125:", i)]
        self.assertIn("Achievement.Reset();", block)
        self.assertIn("VF2ReconcileCareerRoomGoals();", block,
                      "Reset Achievements wipes the records while the upgrades stay "
                      "owned; without the recompute the career-room goals never return")
        self.assertLess(block.index("Achievement.Reset();"), block.index("VF2ReconcileCareerRoomGoals();"))
        self.assertLess(block.index("VF2PersistentAIBathroom2Mask() = aiBathroom2;"),
                        block.index("VF2ReconcileCareerRoomGoals();"),
                        "recompute must follow the mask restores")

    def test_the_patch_is_wired_after_the_achiever_hook(self):
        src = _source()
        self.assertIn("def patch_career_room_goal_reconciliation(manifest):", src)
        self.assertIn("    patch_achiever_load_reconciliation(manifest)\n    patch_career_room_goal_reconciliation(manifest)\n", src)
        self.assertEqual(patcher.CAREER_ROOM_GOALS_LOAD_HELPER_SYMBOL, HELPER)


class TheObject(unittest.TestCase):
    """The patch is relocation-only and lands on exactly the CTech site."""

    def test_only_the_ctech_load_relocation_changes(self):
        if not (patcher.SRC_OBJS / "theGameState.obj").is_file():
            self.skipTest("missing build input theGameState.obj")
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = pathlib.Path(tmp)
                patcher.PATCHED = temp_root
                target = temp_root / "theGameState.obj"
                shutil.copy2(patcher.SRC_OBJS / "theGameState.obj", target)
                before = CoffObject(target)
                lb = before.symbol(LOAD)
                sb = before.section(lb.section)
                bytes_before = bytes(before.buf[sb.raw_ptr: sb.raw_ptr + sb.raw_size])
                relocs_before = {}
                for index in range(sb.nreloc):
                    v, si, rt = struct.unpack_from("<IIH", before.buf, sb.reloc_ptr + index * 10)
                    relocs_before[v] = (before.symbol_by_index[si].name, rt)

                manifest = {}
                patcher.patch_career_room_goal_reconciliation(manifest)

                after = CoffObject(target)
                la = after.symbol(LOAD)
                sa = after.section(la.section)
                self.assertEqual(bytes(after.buf[sa.raw_ptr: sa.raw_ptr + sa.raw_size]), bytes_before,
                                 "the section bytes changed; this hook must be relocation-only")
                changed = []
                for index in range(sa.nreloc):
                    v, si, rt = struct.unpack_from("<IIH", after.buf, sa.reloc_ptr + index * 10)
                    now = (after.symbol_by_index[si].name, rt)
                    if relocs_before.get(v) != now:
                        changed.append((v - la.value, relocs_before.get(v), now))
                self.assertEqual(changed, [(0x206, (NATIVE, IMAGE_REL_I386_REL32), (HELPER, IMAGE_REL_I386_REL32))],
                                 "exactly one relocation must change: Load+0x206, native CTech::LoadState -> the wrapper")
                self.assertEqual(manifest["CareerRoomGoalReconciliation"]["achievement_ids"], ["0x36", "0x37", "0x38"])
        finally:
            patcher.PATCHED = old_patched


if __name__ == "__main__":
    unittest.main()
