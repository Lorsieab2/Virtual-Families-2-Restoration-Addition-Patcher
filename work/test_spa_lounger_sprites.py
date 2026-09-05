#!/usr/bin/env python3
"""Both Spa Loungers wear the same sprite; only the invisible one may vanish.

The owner's rule, stated after the Invisible Spa Lounger was found shipping a
generic brown chaise:

    Invisible furniture has visible patches with the "Visible Furniture
    Sprites" patch. THAT'S what I want you to install the spalounger.png for
    regarding the invisible Spa Lounger item. When the "transparent graphics"
    patch is enabled, the patcher should swap ONLY the invisible furniture's
    sprites with a fully-transparent version.

    For the Normal Spa Lounger, I want it to have the same spalounger.png
    sprite. This one should not become transparent under any circumstances.

So "invisible" names which item the transparency patch may blank -- it is not
an absence of artwork. Both items are the same piece of furniture and look
identical until that patch is turned on.

Two mistakes this guards against, and the first already shipped:

  * Giving the invisible item no art of its own, or a stand-in. A player who
    bought the Invisible Spa Lounger and enabled Visible Graphics saw a brown
    chaise, which is not the thing they purchased.
  * Scoping the transparency swap by ARTWORK rather than by ITEM. The two
    loungers share one sprite file, so a swap keyed on the filename would
    blank the normal Spa Lounger too -- silently removing a visible item the
    player paid a store price for.
"""
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

SPRITE = "SpaLoungerStd.png"
INVISIBLE = "InvisibleSpaLounger"
NORMAL = "SpaLoungerStd"


def _by_name(table, name):
    for item in table:
        if item["name"] == name:
            return item
    return None


class TestBothLoungersShareTheSprite(unittest.TestCase):
    def test_the_invisible_one_ships_the_spa_lounger_art(self):
        item = _by_name(patcher.INVISIBLE_OUTDOOR_ITEMS, INVISIBLE)
        self.assertIsNotNone(item, f"{INVISIBLE} is gone from the invisible set")
        self.assertEqual(
            item.get("source_png"), SPRITE,
            "the invisible Spa Lounger must ship the Spa Lounger's own art "
            "under Visible Graphics, not a stand-in chaise",
        )
        self.assertEqual(item.get("base_png"), SPRITE)

    def test_the_normal_one_ships_the_same_sprite(self):
        item = _by_name(patcher.NEW_FURNITURE_ITEMS, NORMAL)
        self.assertIsNotNone(item, f"{NORMAL} is gone from the furniture set")
        self.assertEqual(item.get("art_png"), SPRITE)

    def test_the_art_is_tracked_in_the_repository(self):
        """It is owner-supplied and cannot be regenerated.

        A sprite resolved from outside the repo would work on the machine that
        has it and fail everywhere else, which is the owner's standing rule
        about not depending on files only they hold.
        """
        tracked = Path(patcher.ROOT) / "patcher_assets" / "new_furniture_art" / SPRITE
        self.assertTrue(tracked.is_file(), f"{SPRITE} is not tracked in the repo")


class TestOnlyTheInvisibleOneCanBeBlanked(unittest.TestCase):
    def test_the_normal_lounger_is_not_in_any_transparency_set(self):
        """The rule the owner was most explicit about.

        Checked against the sets the swap actually iterates, rather than
        against the swap's code, so adding the item to a set fails here even
        if the swap itself is untouched.
        """
        for table_name in (
            "INVISIBLE_OUTDOOR_ITEMS",
            "INVISIBLE_TRANSPARENT_BASE_ITEMS",
        ):
            table = getattr(patcher, table_name, [])
            with self.subTest(table_name):
                self.assertNotIn(
                    NORMAL, [item["name"] for item in table],
                    f"{NORMAL} must never be made transparent",
                )

    def test_the_invisible_lounger_is_in_exactly_one_of_them(self):
        present = [
            name for name in
            ("INVISIBLE_OUTDOOR_ITEMS", "INVISIBLE_TRANSPARENT_BASE_ITEMS")
            if INVISIBLE in [i["name"] for i in getattr(patcher, name, [])]
        ]
        self.assertEqual(
            present, ["INVISIBLE_OUTDOOR_ITEMS"],
            "the invisible Spa Lounger should be blankable through exactly one "
            f"set; found {present}",
        )

    def test_the_swap_is_keyed_by_item_not_by_filename(self):
        """Both loungers share one sprite, so filename keying blanks both.

        The mapping the transparency pipeline consults is built from item
        names. If it were ever rebuilt from source filenames, the normal Spa
        Lounger would disappear along with the invisible one and nothing else
        here would notice.
        """
        mapping = patcher.INVISIBLE_BASE_GRAPHIC_SOURCE_BY_NAME
        self.assertIn(INVISIBLE, mapping, "the invisible item is keyed by name")
        self.assertNotIn(
            NORMAL, mapping,
            "the normal Spa Lounger must not appear in the invisible-graphics "
            "map at all",
        )
        self.assertEqual(mapping[INVISIBLE], SPRITE)


class TestTheSpriteReachesTheBuild(unittest.TestCase):
    """Source is not the artifact. Check the build output.

    The first attempt at this fix changed the item definition and the tests
    passed, while the build kept emitting a brown chaise: the sprite sync
    searched only inherited_runtime_images and the Spa Lounger's art lives in
    new_furniture_art, so a stale seeded copy satisfied it with no error.

    That is the failure the owner warned about -- claiming a bug is fixed when
    the shipped build still has it -- so this reads the build output.
    """

    OUT = Path(patcher.ROOT) / "outputs"
    REFERENCE = (
        Path(patcher.ROOT) / "patcher_assets" / "new_furniture_art" / SPRITE
    )

    def _latest_furniture_dir(self):
        candidates = sorted(
            (p for p in self.OUT.glob("*/Images/Furniture")
             if (p / f"{INVISIBLE}.png").is_file()),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if not candidates:
            self.skipTest("no build output with the invisible lounger present")
        return candidates[0]

    def test_both_loungers_ship_the_owner_sprite_byte_for_byte(self):
        import hashlib

        furniture = self._latest_furniture_dir()
        expected = hashlib.sha256(self.REFERENCE.read_bytes()).hexdigest()
        for name in (f"{INVISIBLE}.png", SPRITE):
            with self.subTest(name):
                built = furniture / name
                self.assertTrue(built.is_file(), f"{name} missing from the build")
                self.assertEqual(
                    hashlib.sha256(built.read_bytes()).hexdigest(), expected,
                    f"{name} in the build is not the owner's sprite",
                )

    def test_only_the_invisible_one_has_a_transparent_variant(self):
        """The ORIGINAL file is what the transparency patch swaps in.

        Its presence for the normal lounger would mean that item could be
        blanked, which the owner ruled out under any circumstances.
        """
        furniture = self._latest_furniture_dir()
        self.assertTrue(
            (furniture / f"{INVISIBLE}.pngORIGINAL").is_file(),
            "the invisible lounger has no transparent variant to swap in",
        )
        self.assertFalse(
            (furniture / f"{SPRITE}ORIGINAL").is_file(),
            "the normal Spa Lounger has a transparent variant; it must never "
            "be blankable",
        )


if __name__ == "__main__":
    unittest.main()
