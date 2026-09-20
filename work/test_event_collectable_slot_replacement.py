"""Event collectable spawns replace the oldest unpicked collectable.

Owner report: the mobile "Interesting Article about Fossils" email never left
a fossil mound in the yard. Owner decision: "fossil email (and any other event
that spawns collectibles) = replace the oldest unpicked collectible".

MECHANISM, pinned below from CollectableItem.obj and confirmed live:

  * CCollectableItem::Add(carrying, point, force) keeps exactly two event
    slots at +0x34C and +0x368 (0x1C apart). With force == false it searches
    those two for a free one and returns WITHOUT SPAWNING when both are busy;
    with force == true it always writes slot 0.
  * Activation writes +0 (active), +8 (spawn stamp: seconds + 0x78) and +0x14
    (carrier, -1 = nobody walking to it).
  * Remove(slot) with slot < 2 clears exactly that event slot.
  * Natural spawns keep the pair busy most of the time. Live in the probe:
    with a natural fossil and a shell in the two slots the fossil email
    spawned nothing; with both slots free it put carrying 105 at (1467, 1861).

FIX: one helper for every EVENT spawn: use a free slot if there is one, else
free the slot nobody is walking to, else the older one; the native force
path keeps slot 0 as its target but moves the survivor aside first. The
mobile fossil event calls the helper directly; the three native event sites
(Bug Whisperer x2, Neighbor Collectible x1) are retargeted by relocation to a
__thiscall-shaped thunk. CCollectableItem::Update's natural spawn is left
alone on purpose.
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

NATIVE_ADD = "?Add@CCollectableItem@@QAEXW4ECarrying@@UldwPoint@@_N@Z"
THUNK = "_VF2EventCollectableAdd"
SITES = (
    ("?ImpactGame@CEventTheBugWhisperer@@UAEXH@Z", 0x7D),
    ("?ImpactGame@CEventTheBugWhisperer@@UAEXH@Z", 0xB8),
    ("?ImpactGame@CEventTheNeighborCollectible@@UAEXXZ", 0x0E),
)


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


def _body(obj_name, symbol):
    obj = CoffObject(patcher.SRC_OBJS / obj_name)
    s = obj.symbol(symbol)
    sec = obj.section(s.section)
    return bytes(obj.buf[sec.raw_ptr + s.value: sec.raw_ptr + sec.raw_size]), obj, s, sec


def _reloc_target(obj, sec, vaddr):
    for index in range(sec.nreloc):
        v, symbol_index, rtype = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + index * 10)
        if v == vaddr:
            return obj.symbol_by_index[symbol_index].name, rtype
    return None


class GroundTruth(unittest.TestCase):
    """Pinned to the stock objects so the two-slot model is never re-derived."""

    def setUp(self):
        for name in ("CollectableItem.obj", "IslandEvents.obj"):
            if not (patcher.SRC_OBJS / name).is_file():
                self.skipTest("missing build input %s" % name)

    def test_add_searches_exactly_two_event_slots_from_0x34c(self):
        body, *_ = _body("CollectableItem.obj", NATIVE_ADD)
        self.assertIn(b"\x8D\x83\x4C\x03\x00\x00", body[:0x20], "lea eax,[ebx+34Ch] -- the first event slot")
        self.assertIn(b"\x83\xC0\x1C\x83\xFF\x02\x7C", body[:0x30], "add eax,1Ch / cmp edi,2 / jl -- two slots, then give up")
        # The give-up path returns before any store: ret 10h right after the loop.
        self.assertIn(b"\x5F\x5B\x8B\xE5\x5D\xC2\x10\x00", body[:0x30])

    def test_activation_writes_active_stamp_and_carrier(self):
        body, *_ = _body("CollectableItem.obj", NATIVE_ADD)
        self.assertIn(b"\xC6\x86\x4C\x03\x00\x00\x01", body, "mov byte ptr [esi+34Ch],1")
        self.assertIn(b"\x83\xC0\x78", body, "stamp = seconds + 0x78")
        self.assertIn(b"\xC7\x86\x60\x03\x00\x00\xFF\xFF\xFF\xFF", body, "carrier = -1 at +0x14")
        self.assertIn(b"\x89\x86\x54\x03\x00\x00", body, "stamp stored at +0x08")

    def test_an_explicit_carrying_activates_unconditionally_once_a_slot_is_free(self):
        """The duplicate checks (WasItemSpawned / IsItemBeingCarried /
        WasTabletCollected) sit on the RANDOM path only. With an explicit
        carrying, Add stores the record and jumps straight to the activation
        block, so once the helper has freed a slot the native spawn cannot be
        rejected. Review question answered from the bytes, not from intent."""
        body, obj, s, sec = _body("CollectableItem.obj", NATIVE_ADD)
        explicit = body.index(b"\x89\x86\x5C\x03\x00\x00\xE9")  # mov [esi+35Ch],eax ; jmp rel32
        rel = struct.unpack_from("<i", body, explicit + 7)[0]
        target = explicit + 7 + 4 + rel
        self.assertEqual(body[target:target + 7], b"\xC6\x86\x4C\x03\x00\x00\x01",
                         "the explicit path's jump lands on mov byte ptr [esi+34Ch],1 -- activation")
        checks = []
        for index in range(sec.nreloc):
            v, si, rt = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + index * 10)
            name = obj.symbol_by_index[si].name
            if s.value <= v < s.value + len(body) and any(k in name for k in ("WasItemSpawned", "IsItemBeingCarried", "WasTabletCollected")):
                checks.append(v - s.value)
        self.assertEqual(len(checks), 3, checks)
        for offset in sorted(checks):
            self.assertGreater(offset, explicit, "a duplicate check sits before the explicit path's jump")
            self.assertLess(offset, target, "a duplicate check sits after the activation block")
        # The random path reaches those checks only when force is false:
        # test cl,cl / jne activation right before the first of them.
        first = min(checks)
        self.assertIn(b"\x84\xC9\x75", body[first - 0x14:first])

    def test_remove_clears_an_event_slot_for_indices_below_two(self):
        body, *_ = _body("CollectableItem.obj", "?Remove@CCollectableItem@@QAEXH@Z")
        self.assertIn(b"\x83\xFA\x02\x7D", body[:0x20], "cmp edx,2 / jge -- slots 0 and 1 are the event slots")
        self.assertIn(b"\xC6\x84\x81\x4C\x03\x00\x00\x00", body, "mov byte ptr [ecx+eax*4+34Ch],0")

    def test_the_three_native_event_sites_are_where_the_generator_expects(self):
        obj = CoffObject(patcher.SRC_OBJS / "IslandEvents.obj")
        for owner_name, call_offset in SITES:
            with self.subTest(site=owner_name, offset=hex(call_offset)):
                owner = obj.symbol(owner_name)
                sec = obj.section(owner.section)
                self.assertEqual(obj.buf[sec.raw_ptr + owner.value + call_offset - 1], 0xE8)
                self.assertEqual(_reloc_target(obj, sec, owner.value + call_offset), (NATIVE_ADD, IMAGE_REL_I386_REL32))
        # And there are no others outside CCollectableItem itself.
        self.assertEqual(patcher.EVENT_COLLECTABLE_NATIVE_SITES, SITES)

    def test_neighbor_collectible_forces_and_bug_whisperer_does_not(self):
        body, obj, s, sec = _body("IslandEvents.obj", "?ImpactGame@CEventTheNeighborCollectible@@UAEXXZ")
        self.assertEqual(body[:0x0D], b"\x6A\x01\x6A\x00\x6A\x00\x6A\xFF\xB9" + body[9:0x0D], "push 1 (force) / push 0 / push 0 / push -1 (random)")
        bug, *_ = _body("IslandEvents.obj", "?ImpactGame@CEventTheBugWhisperer@@UAEXH@Z")
        self.assertIn(b"\x6A\x00\x56\x50\x6A\x0C", bug, "push 0 (no force) / push esi / push eax / push 0Ch")


class TheSource(unittest.TestCase):
    def test_the_collectable_class_declares_add_and_remove(self):
        src = _strip_comments(_source())
        self.assertIn("    void Add(ECarrying carrying, ldwPoint point, bool force);\n    void Remove(int slot);\n\n    char pad0[0x8A8];", src)

    def test_the_victim_is_the_unpicked_slot_then_the_older_one(self):
        src = _strip_comments(_source())
        f = _function(src, "static int VF2EventCollectableVictim()")
        self.assertIn("if (picked0 != picked1) return picked0 ? 1 : 0;", f)
        self.assertIn("return VF2EventCollectableSlotStamp(1) < VF2EventCollectableSlotStamp(0) ? 1 : 0;", f)
        self.assertIn("+ 0x34C + slot * 0x1C", _function(src, "static unsigned char *VF2EventCollectableSlot(int slot)"))
        self.assertIn("+ 0x14) != -1", _function(src, "static bool VF2EventCollectableSlotPicked(int slot)"))
        self.assertIn("+ 0x08)", _function(src, "static unsigned int VF2EventCollectableSlotStamp(int slot)"))

    def test_the_helper_frees_only_when_both_slots_are_busy(self):
        src = _strip_comments(_source())
        f = _function(src, 'extern "C" void __cdecl VF2EventCollectableAddImpl(')
        self.assertIn("} else if (busy0 && busy1) {\n        collectables->Remove(VF2EventCollectableVictim());\n    }", f)
        # force path: a busy slot 0 is moved aside rather than overwritten.
        self.assertIn("if (busy0 && !busy1) {\n            VF2MoveEventCollectableSlot(0, 1);", f)
        self.assertIn("if (VF2EventCollectableVictim() == 1) {\n                VF2MoveEventCollectableSlot(0, 1);\n            } else {\n                collectables->Remove(0);\n            }", f)
        self.assertIn("collectables->Add((ECarrying)carrying, point, force != 0);", f)
        self.assertLess(f.index("Remove("), f.index("->Add("), "the slot is freed before the native spawn")

    def test_the_thunk_forwards_four_words_and_ecx_and_pops_sixteen(self):
        src = _strip_comments(_source())
        f = _function(src, 'extern "C" __declspec(naked) void VF2EventCollectableAdd()')
        self.assertEqual(f.count("push dword ptr [esp+16]"), 4)
        self.assertIn("push ecx\n        call VF2EventCollectableAddImpl\n        add esp, 20\n        ret 16", f)

    def test_the_mobile_fossil_event_uses_the_helper(self):
        src = _strip_comments(_source())
        i = src.index("}} else if (outcome_kind_ == 13) {{")
        block = src[i:src.index("}} else if (outcome_kind_ == 20) {{", i)]
        self.assertIn("VF2EventCollectableAddImpl(&CollectableItem, (int)carrying, point.x, point.y, 0);", block)
        self.assertNotIn("CollectableItem.Add(", block, "the raw two-slot Add must not be called by the event")
        self.assertIn("ldwGameState::GetRandom(12) + 103", block, "still one random fossil")
        self.assertIn("ldwGameState::GetRandom(260) + 1212", block)
        self.assertIn("ldwGameState::GetRandom(126) + 1829", block)
        self.assertIn('extern "C" void __cdecl VF2EventCollectableAddImpl(void *item, int carrying, int x, int y, int force);', src)

    def test_the_patch_is_wired_for_every_variant(self):
        src = _source()
        self.assertIn("def patch_event_collectable_slot_replacement(manifest):", src)
        self.assertIn("    patch_career_room_goal_reconciliation(manifest)\n    patch_event_collectable_slot_replacement(manifest)\n", src)
        self.assertEqual(patcher.EVENT_COLLECTABLE_ADD_THUNK_SYMBOL, THUNK)

    def test_natural_spawns_are_untouched(self):
        src = _source()
        self.assertNotIn("?Update@CCollectableItem@@QAEXXZ", src.split("def patch_event_collectable_slot_replacement", 1)[1].split("\ndef ", 1)[0])


class TheObject(unittest.TestCase):
    def test_exactly_the_three_native_relocations_change(self):
        if not (patcher.SRC_OBJS / "IslandEvents.obj").is_file():
            self.skipTest("missing build input IslandEvents.obj")
        old_patched = patcher.PATCHED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                temp_root = pathlib.Path(tmp)
                patcher.PATCHED = temp_root
                target = temp_root / "IslandEvents.obj"
                shutil.copy2(patcher.SRC_OBJS / "IslandEvents.obj", target)
                before = CoffObject(target)
                relocs_before = {}
                sections_before = {}
                for sec in before.sections:
                    # Sections without raw data (raw_ptr == 0) would compare the file header.
                    sections_before[sec.index] = bytes(before.buf[sec.raw_ptr: sec.raw_ptr + sec.raw_size]) if sec.raw_size and sec.raw_ptr else b""
                    for index in range(sec.nreloc):
                        v, si, rt = struct.unpack_from("<IIH", before.buf, sec.reloc_ptr + index * 10)
                        relocs_before[(sec.index, v)] = (before.symbol_by_index[si].name, rt)
                manifest = {}
                patcher.patch_event_collectable_slot_replacement(manifest)
                after = CoffObject(target)
                changed = []
                for sec in after.sections:
                    if sec.raw_size and sec.raw_ptr:
                        self.assertEqual(bytes(after.buf[sec.raw_ptr: sec.raw_ptr + sec.raw_size]), sections_before[sec.index], "section bytes changed; relocation-only")
                    for index in range(sec.nreloc):
                        v, si, rt = struct.unpack_from("<IIH", after.buf, sec.reloc_ptr + index * 10)
                        now = (after.symbol_by_index[si].name, rt)
                        if relocs_before.get((sec.index, v)) != now:
                            changed.append((relocs_before.get((sec.index, v)), now))
                self.assertEqual(len(changed), 3)
                for was, now in changed:
                    self.assertEqual(was, (NATIVE_ADD, IMAGE_REL_I386_REL32))
                    self.assertEqual(now, (THUNK, IMAGE_REL_I386_REL32))
                self.assertEqual(len(manifest["EventCollectableSlotReplacement"]["native_sites"]), 3)
        finally:
            patcher.PATCHED = old_patched


class TheEmittedSources(unittest.TestCase):
    def test_the_emitted_units_carry_the_helper_and_the_call(self):
        special = patcher.PATCHED / "vf2_special_upgrade_effects.cpp"
        island = patcher.PATCHED / "vf2_island_events.cpp"
        if not special.is_file() or not island.is_file():
            self.skipTest("generator output not present; run the generator first")
        self.assertIn("VF2EventCollectableAddImpl(", special.read_text(encoding="utf-8", errors="replace"))
        text = island.read_text(encoding="utf-8", errors="replace")
        if "CMobileIslandEvent" in text:
            self.assertIn("VF2EventCollectableAddImpl(&CollectableItem, (int)carrying, point.x, point.y, 0);", text)
            self.assertIsNone(re.search(r"CollectableItem\.Add\(carrying, point, false\)", text))


if __name__ == "__main__":
    unittest.main()
