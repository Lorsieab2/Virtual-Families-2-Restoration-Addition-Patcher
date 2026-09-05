#!/usr/bin/env python3
"""The supplied prop art is tracked, and pinned to what was supplied.

The owner provided meal and drinks sprites for the Picnic and Patio Tables --
the artwork half of a request that has been blocked since B156. Art arriving
by hand is exactly the kind of input that goes missing or gets silently
resized, so it is checked in and hash-pinned here rather than left in a
Downloads folder.

These are world props, so they follow the engine's own convention: an
orientation PAIR per prop, RGBA, at the scale of existing placed props such as
PetBowlsFull_SE (62x35). The drinks prop has a single sprite because the patio
drinks stand reads the same from either side.

This does NOT mean the props render yet. CEnvironment::SetProp accepts ids
0x00-0x54 and the two props are 0x55 and 0x56, so the ids never reach the
engine at all -- VF2PatioSetPropAndTrack intercepts them and tracks the state
externally. Drawing is still to be built. The art being present and correct is
a precondition for that work, not evidence it is done.
"""
import hashlib
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = (
    ROOT / "patcher_assets" / "optional_patches" / "mobile_furniture_behaviors"
    / "prop_art"
)

# name -> (width, height, sha256)
SUPPLIED = {
    "mealSE.png": (105, 71, "807906bc2f3c9f5f"),
    "mealSW.png": (115, 67, "4e6326afc3515b61"),
    "patioDrinks.png": (44, 39, "2f932475499c24d6"),
}


def _png(path):
    data = path.read_bytes()
    width, height = struct.unpack_from(">II", data, 16)
    return width, height, data[25], hashlib.sha256(data).hexdigest()[:16]


class TestSuppliedPropArt(unittest.TestCase):
    def test_every_supplied_sprite_is_checked_in(self):
        for name in SUPPLIED:
            with self.subTest(name):
                self.assertTrue(
                    (ART / name).is_file(),
                    f"{name} is missing; the owner supplied it by hand and it "
                    "cannot be regenerated",
                )

    def test_the_sprites_are_the_ones_that_were_supplied(self):
        for name, (width, height, digest) in SUPPLIED.items():
            with self.subTest(name):
                got_w, got_h, colour_type, got_sha = _png(ART / name)
                self.assertEqual((got_w, got_h), (width, height),
                                 f"{name} has been resized")
                self.assertEqual(got_sha, digest, f"{name} has been re-encoded")
                # 6 = RGBA. A prop drawn over the world needs its alpha.
                self.assertEqual(colour_type, 6, f"{name} lost its alpha channel")

    def test_the_meal_prop_keeps_both_orientations(self):
        """A world prop without its pair renders wrong from one side."""
        for suffix in ("SE", "SW"):
            with self.subTest(suffix):
                self.assertIn(f"meal{suffix}.png", SUPPLIED)


if __name__ == "__main__":
    unittest.main()
