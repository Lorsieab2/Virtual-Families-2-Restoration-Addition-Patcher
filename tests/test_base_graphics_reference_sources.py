#!/usr/bin/env python3
"""Base Graphics must be able to find every invisible item's base art.

The Base Graphics reference set is what a player restores their visible art
from after applying Transparent Graphics. An item missing from it cannot be
restored -- the player is left stuck with an invisible object they paid a store
price for.

sync_invisible_furniture_reference_sets() resolves each item's base image from
OUT first, and falls back to tracked sources when OUT does not have it yet.
That fallback searched only `inherited_runtime_images` and the vanilla runtime
payload, so ADDED art -- art that is neither inherited nor vanilla -- could not
be found at all.

The Invisible Spa Lounger is the case that proves it. Its base is
SpaLoungerStd.png, which exists ONLY in patcher_assets/new_furniture_art:

    inherited_runtime_images     absent
    vanilla payload              absent
    new_furniture_art            PRESENT   <- and was not searched

Ordering is what makes this reachable rather than theoretical:
sync_invisible_furniture_reference_sets() runs at generator line ~35221 and
install_new_furniture_art() -- which writes that art into OUT -- runs at ~35289.
The sync happens first, so on a clean output tree the art is not in OUT yet and
the fallback is the only way to find it.
"""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import patch_mobile_furniture_pack as patcher

SOURCE = ROOT / "work" / "patch_mobile_furniture_pack.py"


class BaseGraphicsCanResolveAddedArt(unittest.TestCase):
    def test_the_fallback_searches_the_new_art_directory(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("def sync_invisible_furniture_reference_sets(")
        body = source[start:source.index("\ndef ", start + 10)]
        self.assertIn(
            "NEW_FURNITURE_ART_DIR", body,
            "the Base Graphics fallback does not search new_furniture_art, so "
            "an invisible item whose base is ADDED art is dropped from the "
            "reference set and can never be restored",
        )

    def test_every_invisible_items_base_is_findable_somewhere_tracked(self):
        """Not just the Spa Lounger -- every one of them.

        Only tracked locations count. The vanilla payload is a gitignored build
        input, so a source that exists only there would fail on a fresh clone.
        """
        tracked = [
            ROOT / "patcher_assets" / "inherited_runtime_images" / "Furniture",
            patcher.NEW_FURNITURE_ART_DIR,
        ]
        payload_dirs = [
            Path(p) / "Images" / "Furniture"
            for p in patcher.VANILLA_RUNTIME_PAYLOAD_SOURCE_DIRS
        ]
        unfindable = []
        for name, source_name in sorted(
            patcher.INVISIBLE_BASE_GRAPHIC_SOURCE_BY_NAME.items()
        ):
            if any((d / source_name).is_file() for d in tracked):
                continue
            if any(d.is_dir() for d in payload_dirs):
                if any((d / source_name).is_file() for d in payload_dirs):
                    continue
            else:
                # Payload absent (fresh clone): cannot judge these, skip them
                # rather than fail on a gitignored build input.
                continue
            unfindable.append(f"{name} -> {source_name}")
        self.assertEqual(
            unfindable, [],
            "these invisible items' base art cannot be found in any searched "
            "location, so Base Graphics would omit them:\n  "
            + "\n  ".join(unfindable),
        )

    def test_the_spa_lounger_base_is_only_in_the_new_art_directory(self):
        """Pins WHY the new entry is required, so it is not removed as noise."""
        source_name = patcher.INVISIBLE_BASE_GRAPHIC_SOURCE_BY_NAME.get(
            "InvisibleSpaLounger"
        )
        self.assertEqual(source_name, "SpaLoungerStd.png")
        self.assertTrue(
            (patcher.NEW_FURNITURE_ART_DIR / source_name).is_file(),
            "SpaLoungerStd.png is not in new_furniture_art",
        )
        self.assertFalse(
            (ROOT / "patcher_assets" / "inherited_runtime_images"
             / "Furniture" / source_name).is_file(),
            "SpaLoungerStd.png is now also in inherited_runtime_images; if it "
            "moved, this test's premise needs rechecking rather than deleting",
        )


if __name__ == "__main__":
    unittest.main()
