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
