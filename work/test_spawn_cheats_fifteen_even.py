"""The two spawn cheats spawn fifteen each, evenly split across their types.

Owner: "they should each spawn 15 of each category of trash (comprised of
equal amounts of dirt smudges, socks and wrappers) and weeds (equal numbers
of each type of weed) respectively."

MECHANISM, pinned below from CollectableItem.obj: the four native spawners
(SpawnStainInHouse, SpawnSockInHouse, SpawnTrashInHouse, SpawnWeedsInYard)
each take the FIRST FREE of the 30 junk slots at +4 (0x1C apart), mark it
active, set carrier -1, pick a RANDOM sub-type from a fixed base, bump
their spawn counter (+0x8B4 for the three house spawners, +0x8B0 for
SpawnWeedsInYard) and place the item for their material. The old cheats
called them with 10/10/10 and 30, so the split was random.

FIX: spawn one item at a time through the native routine and then pin the
sub-type of the slot it just filled. Trash: 15 items cycling smudge, sock,
wrapper (5 each), sub-types cycling within each category. Weeds: 15 items
cycling the four weed types (4/4/4/3; fifteen is not divisible by four).
The cycle positions live outside the functions and advance only after a
successful spawn, so successive presses continue where the last one
stopped: all six sock sub-types are reached and the weed type that gets
three rotates.
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"
sys.path.insert(0, str(ROOT / "work"))

import patch_mobile_furniture_pack as patcher  # noqa: E402
from coff_patch import CoffObject  # noqa: E402


def _source():
    return GEN.read_text(encoding="utf-8")


def _strip_comments(text):
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        out.append(line.split("//")[0] if "//" in line else line)
    return "\n".join(out)


def _function(src, signature_start):
    i = src.index(signature_start)
    close = src.index(")", i)
    end = src.index("\n}\n", close)
    return src[i:end]


def _body(symbol):
    obj = CoffObject(patcher.SRC_OBJS / "CollectableItem.obj")
    s = obj.symbol(symbol)
    sec = obj.section(s.section)
    return bytes(obj.buf[sec.raw_ptr + s.value: sec.raw_ptr + sec.raw_size])


class GroundTruth(unittest.TestCase):
    """The native spawners: first free slot, random sub-type from a base."""

    def setUp(self):
        if not (patcher.SRC_OBJS / "CollectableItem.obj").is_file():
            self.skipTest("missing build input CollectableItem.obj")

    def test_each_spawner_takes_the_first_free_slot_and_rolls_its_subtype(self):
        rows = (
            ("?SpawnStainInHouse@CCollectableItem@@QAEXH@Z", 3, 0x83, 0x8B4),
            ("?SpawnSockInHouse@CCollectableItem@@QAEXH@Z", 6, 0x73, 0x8B4),
            ("?SpawnTrashInHouse@CCollectableItem@@QAEXH@Z", 4, 0x79, 0x8B4),
            ("?SpawnWeedsInYard@CCollectableItem@@QAEXH@Z", 4, 0x7D, 0x8B0),
        )
        for symbol, subtypes, base, counter in rows:
            with self.subTest(symbol=symbol):
                body = _body(symbol)
                # inc dword ptr [eax+counter]: the house spawners share +0x8B4,
                # the yard spawner keeps its own +0x8B0.
                self.assertIn(b"\xFF\x80" + counter.to_bytes(4, "little"), body, "spawn counter offset")
                other = 0x8B0 if counter == 0x8B4 else 0x8B4
                self.assertNotIn(b"\xFF\x80" + other.to_bytes(4, "little"), body)
                self.assertIn(b"\x8D\x71\x04", body[:0x14], "lea esi,[ecx+4] -- slot 0")
                self.assertIn(b"\x80\x3E\x00\x75", body[:0x20], "cmp byte ptr [esi],0 / jne -- first FREE slot")
                self.assertIn(b"\x6A" + bytes([subtypes]) + b"\xC6\x06\x01", body, "push n / mov byte ptr [esi],1")
                # add eax,base: imm8 when base fits a signed byte, imm32 otherwise (0x83 does not).
                encodings = (b"\x83\xC0" + bytes([base]), b"\x05" + bytes([base, 0, 0, 0]))
                self.assertTrue(any(e in body for e in encodings), "add eax,base -- random sub-type")
                self.assertIn(b"\xC7\x46\x14\xFF\xFF\xFF\xFF", body, "carrier -1")
                self.assertIn(b"\x89\x46\x04", body, "carrying stored at +4")
                self.assertIn(b"\x83\xC6\x1C\x83\xFF\x1E\x7C", body, "add esi,1Ch / cmp edi,1Eh / jl -- thirty slots")

    def test_the_category_predicates_bound_the_subtypes(self):
        for symbol, span in (
            ("?IsDirtSmudge@CCollectableItem@@AAE_NAAUSCollectable@1@@Z", 2),
            ("?IsSock@CCollectableItem@@AAE_NAAUSCollectable@1@@Z", 5),
            ("?IsCandyWrapper@CCollectableItem@@AAE_NAAUSCollectable@1@@Z", 3),
            ("?IsWeed@CCollectableItem@@AAE_NAAUSCollectable@1@@Z", 3),
        ):
            with self.subTest(symbol=symbol):
                self.assertIn(b"\x83\xF8" + bytes([span]) + b"\x0F\x96", _body(symbol), "cmp eax,span / setbe")


class TheSource(unittest.TestCase):
    def test_the_cheats_call_the_new_helpers_and_not_the_old_counts(self):
        src = _strip_comments(_source())
        i = src.index("    case 0x12F:")
        block = src[i:src.index("    case 0x131:", i)]
        self.assertIn("VF2SpawnMaxHouseTrash();", block)
        self.assertIn("VF2SpawnMaxYardWeeds();", block)
        for old in ("SpawnTrashInHouse(10)", "SpawnStainInHouse(10)", "SpawnSockInHouse(10)", "SpawnWeedsInYard(30)"):
            self.assertNotIn(old, block, old)

    def test_trash_is_fifteen_split_five_five_five_with_subtypes_cycling(self):
        src = _strip_comments(_source())
        f = _function(src, "static void VF2SpawnMaxHouseTrash()")
        self.assertIn("kCategories[3] = { eVF2JunkSmudge, eVF2JunkSock, eVF2JunkWrapper };", f)
        self.assertIn("kFirst[3] = { 0x83, 0x73, 0x79 };", f)
        self.assertIn("kCount[3] = { 3, 6, 4 };", f)
        self.assertIn("for (int i = 0; i < 15; ++i) {", f)
        self.assertIn("int const c = i % 3;", f)
        # The cycle position lives outside the function and advances only
        # after a successful spawn, so successive presses continue where the
        # last one stopped and all six sock sub-types are reached.
        self.assertIn("static int gVF2SpawnCheatTrashNext[3] = { 0, 0, 0 };", src)
        self.assertIn("int const carrying = kFirst[c] + gVF2SpawnCheatTrashNext[c];", f)
        self.assertIn("if (!VF2SpawnJunkOfType(kCategories[c], carrying)) return;\n"
                      "        gVF2SpawnCheatTrashNext[c] = (gVF2SpawnCheatTrashNext[c] + 1) % kCount[c];", f)
        self.assertNotIn("int next[3]", f, "a per-press reset would never reach the sixth sock")

    def test_weeds_are_fifteen_cycling_the_four_types(self):
        src = _strip_comments(_source())
        f = _function(src, "static void VF2SpawnMaxYardWeeds()")
        self.assertIn("for (int i = 0; i < 15; ++i) {", f)
        self.assertIn("static int gVF2SpawnCheatWeedNext = 0;", src)
        self.assertIn("if (!VF2SpawnJunkOfType(eVF2JunkWeed, 0x7D + gVF2SpawnCheatWeedNext)) return;\n"
                      "        gVF2SpawnCheatWeedNext = (gVF2SpawnCheatWeedNext + 1) % 4;", f)
        self.assertNotIn("(i % 4)", f, "a per-press restart would always short the same weed type")

    def test_one_item_goes_through_the_native_spawner_then_gets_its_type(self):
        src = _strip_comments(_source())
        f = _function(src, "static bool VF2SpawnJunkOfType(int category, int carrying)")
        self.assertIn("int const slot = VF2FirstFreeJunkSlot();\n    if (slot < 0) return false;", f)
        for category, call in (("eVF2JunkSmudge", "SpawnStainInHouse(1)"), ("eVF2JunkSock", "SpawnSockInHouse(1)"), ("eVF2JunkWrapper", "SpawnTrashInHouse(1)")):
            self.assertIn("case %s: CollectableItem.%s; break;" % (category, call), f)
        self.assertIn("default: CollectableItem.SpawnWeedsInYard(1); break;", f)
        self.assertIn("+ 4 + slot * 0x1C;", f)
        self.assertIn("if (record[0] == 0) return false;", f, "a declined native spawn must not be overwritten")
        self.assertIn("*reinterpret_cast<int *>(record + 4) = carrying;", f)
        self.assertLess(f.index("Spawn"), f.index("= carrying;"), "type is pinned AFTER the native spawn")
        g = _function(src, "static int VF2FirstFreeJunkSlot()")
        self.assertIn("for (int slot = 0; slot < 30; ++slot)", g)
        self.assertIn("if (base[4 + slot * 0x1C] == 0) return slot;", g)

    def test_the_rows_describe_the_new_counts(self):
        rows = {row["item_id"]: row for row in patcher.CHEAT_UPGRADE_ITEMS}
        self.assertIn("Spawns 15: 5 dirt smudges, 5 socks, 5 wrappers", rows[0x12F]["description"])
        self.assertIn("Spawns 15 weeds, all 4 types (4/4/4/3, rotates)", rows[0x130]["description"])
        # The store row field is capped at 90 characters.
        self.assertLessEqual(len(rows[0x12F]["description"]), 90)
        self.assertLessEqual(len(rows[0x130]["description"]), 90)


class TheEmittedSource(unittest.TestCase):
    def test_the_emitted_unit_carries_the_helpers(self):
        emitted = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
        if not emitted.is_file():
            self.skipTest("generator output not present; run the generator first")
        text = emitted.read_text(encoding="utf-8", errors="replace")
        # Stale emitted sources are a failure, not a skip: a green skip here
        # would hide a generator that stopped emitting the helpers.
        self.assertIn("VF2SpawnMaxHouseTrash", text, "emitted sources do not carry the helper; re-run the generator")
        stripped = re.sub(r"(?m)^\s*//[^\n]*\n", "", text)
        self.assertIn("case 0x12F:\n        VF2SpawnMaxHouseTrash();", stripped)
        self.assertIn("case 0x130:\n        VF2SpawnMaxYardWeeds();", stripped)
        self.assertIn("static int gVF2SpawnCheatTrashNext[3] = { 0, 0, 0 };", text)
        self.assertIn("static int gVF2SpawnCheatWeedNext = 0;", text)


if __name__ == "__main__":
    unittest.main()
