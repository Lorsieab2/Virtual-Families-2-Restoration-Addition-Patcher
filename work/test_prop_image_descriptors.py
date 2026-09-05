#!/usr/bin/env python3
"""The prop sprites need DESCRIPTORS, not just reserved space and a draw call.

The picnic meal and patio drinks shipped in B181 with:

  * the art installed into the build's Images folder,
  * the draw helper compiled and its hook installed
    (patch-manifest MobileTablePropDraw status "installed"), and
  * three descriptor records RESERVED for them in the image table.

and still drew nothing, because nothing ever WROTE those three records. They
stayed zero-filled, so the ids prop_art_image_id() computes pointed at blank
descriptors and GetImageGrid() could not resolve any of them.

The artifact-level tell is exact and is what this module pins. Every populated
descriptor carries a path-symbol relocation, so its path string ends up in the
linked executable. In the shipped B181 binary:

    SpaLoungerStd.png   present      <- a populated descriptor
    mealSE.png          ABSENT
    mealSW.png          ABSENT
    patioDrinks.png     ABSENT

"Defined and called" said the feature worked. It did not. Reachable code is not
a working feature when the resources it resolves at runtime were never set up.
"""
import ast
import unittest

NL = chr(10)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "patch_mobile_furniture_pack.py"

import sys
sys.path.insert(0, str(ROOT / "work"))
import patch_mobile_furniture_pack as patcher


class PropDescriptorsArePopulated(unittest.TestCase):
    def test_every_prop_sprite_has_a_descriptor_write(self):
        """Reserving space is not populating it.

        Asserted against the generator's AST rather than a substring: the loop
        must actually iterate PROP_ART_IMAGE_ORDER and call
        append_relocation, which is what binds the path symbol to the record.
        """
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        loops = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.For)
            and isinstance(node.iter, ast.Name)
            and node.iter.id == "PROP_ART_IMAGE_ORDER"
        ]
        self.assertTrue(
            loops,
            "nothing iterates PROP_ART_IMAGE_ORDER to write descriptors, so "
            "the three reserved records stay zero-filled and the sprites "
            "cannot be resolved at runtime",
        )
        calls = {
            node.func.attr
            for loop in loops
            for node in ast.walk(loop)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }
        for required in ("append_undefined_symbol", "append_relocation"):
            self.assertIn(
                required, calls,
                f"the descriptor loop never calls {required}, so the record "
                "carries no path and GetImageGrid cannot load the sprite",
            )

    def test_the_descriptor_path_has_no_images_prefix(self):
        """Descriptor paths are relative to the runtime Images directory.

        Every other block in patch_graphics_manager relies on this:
            head_icon_path      -> "HairstyleIcons/Male_Head_01.png"
            renovation block    -> "MobileRenovations/<file>"
            furniture block     -> "Furniture/<file>"
        and the shipped B181 executable agrees -- it contains
        "HairstyleIcons/" and "Furniture/SpaLoungerStd.png" and contains
        NEITHER with an "Images/" prefix.

        Writing f"Images/{name}" here made GetImageGrid look for
        Images/Images/mealSE.png, which resolves to nothing -- the same
        silent invisibility as having no descriptor at all, and it would
        have survived every other check in this module.
        """
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("for name in PROP_ART_IMAGE_ORDER:")
        body = source[start:start + 1400]
        self.assertNotIn(
            'f"Images/', body,
            "the prop descriptor path carries an Images/ prefix; paths are "
            'already relative to Images, so this resolves to '
            "Images/Images/<file> and the sprite cannot be loaded",
        )

    def test_no_descriptor_block_uses_an_images_prefix(self):
        """The convention, checked across the whole function.

        Pinned for every block rather than just the prop one, because the
        mistake is equally available to the next block somebody adds.
        """
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("def patch_graphics_manager(")
        end = source.index(chr(10) + "def ", start + 10)
        body = source[start:end]
        offenders = [
            line.strip() for line in body.split(chr(10))
            if "path = " in line and '"Images/' in line
        ]
        self.assertEqual(
            offenders, [],
            "these descriptor paths carry an Images/ prefix and would "
            "resolve to Images/Images/...: " + repr(offenders),
        )

    def test_ids_and_install_targets_agree(self):
        """The descriptor path must be the path the art is installed to.

        A descriptor pointing at a path the installer never writes resolves to
        nothing, which fails exactly as silently as no descriptor at all.
        """
        for name in patcher.PROP_ART_IMAGE_ORDER:
            self.assertIn(
                name, patcher.PROP_ART_INSTALL,
                f"{name} has an image id but is never installed",
            )

    def test_the_three_ids_are_distinct_and_consecutive(self):
        ids = [
            patcher.prop_art_image_id(name)
            for name in patcher.PROP_ART_IMAGE_ORDER
        ]
        self.assertEqual(
            len(set(ids)), len(ids),
            "two prop sprites share an image id, so one overwrites the other",
        )
        self.assertEqual(
            ids, list(range(ids[0], ids[0] + len(ids))),
            "the prop ids are not consecutive, so they do not match the "
            "contiguous block reserved for them",
        )




class PropPositionComesFromTheRecord(unittest.TestCase):
    """info.point is the walk-to anchor, not the table.

    Proven from the engine's own instructions rather than assumed.
    CFurnitureManager::FindFurniture ends by copying the matched record into
    sFurnitureInfo2, and it adjusts the position on the way:

        +0x110  sub  esi, [eax]        ; hotspot x
        +0x115  sub  edx, [eax + 4]    ; hotspot y
        +0x121  mov  ecx, [ebx + 0x14] ; record x
        +0x124  mov  eax, [ebx + 0x18] ; record y
        +0x127  add  ecx, esi          ; <-- x + hotspot
        +0x129  add  eax, edx          ; <-- y + hotspot
        +0x137  mov  [edx + 8], ecx    ; info.point.x
        +0x12E  mov  [edx + 0xc], eax  ; info.point.y
        +0x13A  mov  eax, [ebx + 4]
        +0x13D  mov  [edx], eax        ; info.unknown0 = the placement handle

    So info.point is the tile a villager STANDS ON to use the item. Drawing a
    prop there puts it beside the table by however much that furniture map's
    hotspot is offset. The record's own +0x14/+0x18 are the world position, and
    +0x04 is the unique handle that identifies which record was matched.
    """

    def test_the_capture_reads_the_record_not_info_point(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("static void VF2CaptureTableProp(")
        body = source[start:source.index("\n}\n", start)]
        self.assertNotIn(
            "outX = info.point.x", body,
            "the capture is back on info.point, which is the walk-to anchor -- "
            "the prop will draw beside the table, not on it",
        )
        self.assertIn(
            "record + 0x14", body,
            "the capture does not read the placement record's x",
        )
        self.assertIn(
            "record + 0x18", body,
            "the capture does not read the placement record's y",
        )
        # Strip comments first. The explanatory comment above the code
        # mentions info.unknown0, so matching the raw slice stayed green
        # even with the actual comparison deleted -- in which state the
        # loop takes the FIRST active furniture record rather than the
        # one FindFurniture matched.
        code = NL.join(
            line.split("//")[0] for line in body.split(NL)
        )
        self.assertIn(
            "record + 0x04", code,
            "the record is not compared against the placement handle, so "
            "the first active record wins and the wrong table's position "
            "is used when two are placed",
        )
        self.assertIn("info.unknown0", code)


class PropDrawRespectsTheDecalBound(unittest.TestCase):
    """The four-argument AddDecal has no bounds check; this feature adds one.

    Both overloads walk the same free-slot scan:

        +0x008  cmp  byte ptr [esi], dl     ; occupancy byte at record + 0
        +0x010  lea  eax, [eax + 0x18]      ; stride 0x18
        +0x014  cmp  byte ptr [eax], 0
        +0x019  cmp  edx, 0x100 / jg        ; FIVE-arg form only

    The five-argument form skips the write when the array is full. The
    four-argument form has no comparison against any bound and writes wherever
    the scan stopped.

    "At most two extra decals" does not make that safe: it bounds what this
    feature ADDS, not what is already there. With all 256 slots occupied by the
    stock refresh, the first call walks off the end.

    Switching overloads is not the fix -- the five-argument form's extra
    argument is a per-decal value RefreshProps reads from its own object
    ([edi+0x1940] indexed by prop, +0x25BB8), and there is no correct constant
    to substitute. So the bound is applied here instead, against the same array
    with the same stride the engine uses.
    """

    def test_the_draw_checks_the_bound_before_adding(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("static void VF2DrawTableProp(")
        body = source[start:source.index("\n}\n", start)]
        # STRIP COMMENTS FIRST. The explanation above the guard mentions
        # both 0x100 and 0x18, so matching the raw slice stayed green with
        # the actual scan and early return deleted -- which restores the
        # out-of-bounds write this test exists to prevent.
        code = NL.join(line.split("//")[0] for line in body.split(NL))
        self.assertIn(
            "0x100", code,
            "the draw does not bound the decal array in CODE, so a full "
            "array means AddDecal writes past its end",
        )
        self.assertIn(
            "0x18", code,
            "the scan does not use the engine's 0x18 record stride, so it "
            "counts the wrong thing",
        )
        self.assertIn(
            "return", code,
            "there is no early return, so a full array is detected and then "
            "drawn into anyway",
        )
        guard = code.index("0x100")
        call = code.index("Decal.AddDecal")
        self.assertLess(
            guard, call,
            "the bound is checked after the draw, which is no bound at all",
        )


class PropDrawRunsUnconditionally(unittest.TestCase):
    """The draw must not hang off a branch that only sometimes runs.

    The first version of this hook wrapped the last AddDecal call in
    CDecal::RefreshProps. All 48 AddDecal calls in that function sit inside
    per-prop active branches of its switch -- the call at +0xA6A is reached
    only by `jmp 0xa62` from those branches -- so the table props drew only
    while some unrelated stock prop happened to be active.

    CDecal::RefreshDecals calls CDecal::InitDecals as its FIRST instruction,
    before any branch, and runs every refresh. That call is already a five-byte
    call with a relocation, so retargeting it costs zero added bytes.

    InitDecals has two call sites -- RefreshDecals +0x4 and CDecal::Reset
    +0x1C -- so the installer must pick the right one and refuse if the
    prologue ever drifts.
    """

    def test_the_hook_is_on_refreshdecals_not_refreshprops(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("def patch_mobile_table_prop_draw(manifest):")
        body = source[start:source.index("\ndef ", start + 10)]
        self.assertIn(
            "?RefreshDecals@CDecal@@QAEXXZ", body,
            "the prop draw is not hooked through RefreshDecals, so it cannot "
            "be running unconditionally",
        )
        self.assertIn(
            "?RefreshProps@CDecal@@QAEXXZ", body,
            "the tail jump to RefreshProps is not the wrapped site, so the "
            "draw does not run after the stock pass",
        )
        # Mentioning the symbol is not installing the hook. Without the
        # retarget the original jump still runs and nothing draws, while
        # every other assertion in this class stays green.
        self.assertIn(
            "retarget_relocation", body,
            "the installer never retargets the relocation, so the hook "
            "is not actually installed",
        )
        self.assertIn(
            "@VF2RefreshPropsAndTableProps@8", body,
            "the wrapper symbol is never appended, so there is nothing "
            "for the relocation to point at",
        )
        self.assertNotIn(
            "@VF2RefreshPropsAddDecalAndProps@28", body,
            "the old conditional AddDecal wrapper is still installed, so the "
            "props would draw twice whenever a stock prop is active",
        )

    def test_the_installer_refuses_a_drifted_prologue(self):
        """A silent fallback here would re-create the original defect."""
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("def patch_mobile_table_prop_draw(manifest):")
        body = source[start:source.index("\ndef ", start + 10)]
        self.assertIn(
            "decals_sec.raw_size", body,
            "the installer does not require the jump to be the LAST "
            "instruction of RefreshDecals, so the wrapper's return could "
            "land somewhere unintended",
        )
        self.assertIn(
            "raise RuntimeError", body,
            "a drifted prologue does not fail the build",
        )

    def test_the_redundant_wrapper_is_gone(self):
        """Two hooks would draw the props twice per frame."""
        source = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn(
            'extern "C" void __fastcall VF2RefreshPropsAddDecalAndProps(',
            source,
            "the superseded AddDecal wrapper still exists; if it is ever "
            "installed alongside the new hook the props draw twice",
        )


class PropDrawRunsAfterTheStockPass(unittest.TestCase):
    """The capacity check is worthless if it runs against an empty array.

    The draw counts occupied decal slots and refuses at 0x100, because the
    four-argument AddDecal overload has no bounds check of its own. That check
    only means anything at FINAL occupancy.

    An earlier version hooked CDecal::InitDecals -- RefreshDecals' first
    instruction. That is unconditional, which was the point, but InitDecals
    EMPTIES the decal array: the check would always find room, and the two
    added decals would then push the stock pass past the 256-slot end. The
    guard would have read as protection while causing the overflow it was
    written to prevent.

    CDecal::RefreshDecals ends with a tail jump to CDecal::RefreshProps, so
    wrapping that gives a site that is both unconditional and after the whole
    stock pass. The wrapper calls RefreshProps and then draws.
    """

    def test_the_wrapper_calls_the_stock_pass_before_drawing(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("VF2RefreshPropsAndTableProps(CDecal *self")
        body = source[start:source.index("\n}\n", start)]
        stock = body.index("self->RefreshProps()")
        ours = body.index("VF2DrawMobileTableProps()")
        self.assertLess(
            stock, ours,
            "the added props are drawn BEFORE the stock pass, so the decal "
            "capacity check runs against an array the stock pass has not "
            "filled yet -- it would always find room and the stock decals "
            "would overflow instead",
        )

    def test_it_does_not_wrap_initdecals(self):
        """InitDecals is unconditional but empties the array first."""
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("def patch_mobile_table_prop_draw(manifest):")
        body = source[start:source.index("\ndef ", start + 10)]
        self.assertNotIn(
            "@VF2InitDecalsAndProps@8", body,
            "the draw is hooked on InitDecals again; that runs before the "
            "stock pass, so the capacity check sees a freshly emptied array",
        )

if __name__ == "__main__":
    unittest.main()


class DocsDescribeTheInstalledHook(unittest.TestCase):
    """The docs must describe what ships, not an attempt that was rejected.

    The hook moved twice: from a conditional AddDecal call inside
    CDecal::RefreshProps, to CDecal::InitDecals (unconditional but WRONG, since
    it empties the decal array before the capacity check runs), and finally to
    RefreshDecals' tail jump to RefreshProps.

    After the second move the ledger and the transparency log still described
    the InitDecals arrangement -- the very ordering the capacity fix rejected.
    Anyone maintaining or verifying this would have been reading the opposite
    of what is installed, which is worse than no documentation.
    """

    LEDGER = ROOT / "docs" / "REQUEST_LEDGER.md"
    LOG = ROOT / "docs" / "Transparency Log.txt"

    def _prop_text(self):
        row = next(
            line for line in self.LEDGER.read_text(encoding="utf-8").splitlines()
            if line.startswith("| Picnic and patio table props")
        )
        log = self.LOG.read_text(encoding="utf-8")
        entry = log[log.index("B182 the picnic and patio props"):]
        return row, entry.split(NL + "B18", 1)[0]

    def test_both_documents_name_the_installed_hook(self):
        for name, text in zip(("ledger", "transparency log"), self._prop_text()):
            with self.subTest(doc=name):
                self.assertIn(
                    "tail jump", text.lower(),
                    "the document does not name the tail jump that is actually "
                    "hooked",
                )

    def test_neither_presents_initdecals_as_the_installed_hook(self):
        """It may appear only as the rejected attempt it was."""
        for name, text in zip(("ledger", "transparency log"), self._prop_text()):
            with self.subTest(doc=name):
                if "InitDecals" not in text:
                    continue
                lowered = text.lower()
                self.assertTrue(
                    "wrong" in lowered or "rejected" in lowered
                    or "intermediate attempt" in lowered,
                    "InitDecals is mentioned without being marked as the "
                    "rejected arrangement, so it reads as the installed hook -- "
                    "which is the ordering the capacity fix exists to avoid",
                )
