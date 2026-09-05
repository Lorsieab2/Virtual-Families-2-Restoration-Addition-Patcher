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


if __name__ == "__main__":
    unittest.main()


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
        self.assertIn(
            "info.unknown0", body,
            "the record is not identified by the placement handle, so the "
            "wrong table's position could be used when two are placed",
        )


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
        self.assertIn(
            "0x100", body,
            "the draw does not bound the decal array, so a full array means "
            "AddDecal writes past its end",
        )
        self.assertIn(
            "0x18", body,
            "the scan does not use the engine's 0x18 record stride, so it "
            "counts the wrong thing",
        )
        guard = body.index("0x100")
        call = body.index("Decal.AddDecal")
        self.assertLess(
            guard, call,
            "the bound is checked after the draw, which is no bound at all",
        )
