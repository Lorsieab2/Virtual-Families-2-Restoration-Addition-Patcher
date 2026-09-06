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

NL = chr(10)
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import patch_mobile_furniture_pack as patcher

SOURCE = ROOT / "work" / "patch_mobile_furniture_pack.py"



# The base sources that live ONLY in the gitignored vanilla payload, pinned
# by name because a fresh clone cannot look.
#
# Skipping EVERY unresolvable source when the payload is absent made this
# suite report success on exactly the environment it claims to protect: a
# newly added or renamed invisible item whose art was never committed got
# waved through, because 'not in a tracked directory' and 'vanilla-only'
# were treated as the same thing. Only a name on this list gets that excuse,
# so anything NEW must be findable in a tracked directory or it fails.
#
# Every entry was confirmed present in the vanilla payload when this list was
# written, and a test below re-confirms it whenever the payload is available.
VANILLA_ONLY_BASE_SOURCES = frozenset({
    "BedAdultBrownStd.png",
    "ScaleBathroomStd.png",
    "ChairBeanbagBlueStd.png",
    "BedKidsBlueStd.png",
    "DoubleBedCheckeredDuvetBlue.png",
    "DresserStd1.png",
    "LaundryDryingRackStd.png",
    "PoolLargeStd.png",
    "GrandfatherClockStd.png",
    "HammockStd.png",
    "HeartShapedBed.png",
    "IroningBoardStd.png",
    "PoolChildrensStd.png",
    "KidsTableAndChairsStd.png",
    "BookCaseBirchStd.png",
    "IpodSpeakersStd.png",
    "FirePlaceRusticStd.png",
    "PlayStructureStd.png",
    "Sandbox.png",
    "Gothic_SingleBedBlue.png",
    "SofaBlue.png",
    "LowerBookshelf.png",
    "BookCaseBirchSmStd.png",
    "CouchTrashedBeigeStd.png",
    "TrainTableForKids.png",
    "Trampoline.png",
    "SofaWornWhiteStd.png",
    "YogaGearStd.png",
})

class BaseGraphicsCanResolveAddedArt(unittest.TestCase):
    def test_the_fallback_searches_the_new_art_directory(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("def sync_invisible_furniture_reference_sets(")
        body = source[start:source.index("\ndef ", start + 10)]
        # STRIP COMMENTS. This currently passes only because the comment
        # above the fallback entry happens to say "Newly ADDED art" rather
        # than the symbol name -- luck, not design. Three tests in this
        # repository have already matched their own explanatory comment
        # and stayed green with the code deleted, so any test that slices
        # raw source strips comments first.
        code = NL.join(line.split("#")[0] for line in body.split(NL))
        self.assertIn(
            "NEW_FURNITURE_ART_DIR", code,
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
            elif source_name in VANILLA_ONLY_BASE_SOURCES:
                # Payload absent (fresh clone). Only a source on the pinned
                # list below may be excused: each was CONFIRMED present in the
                # vanilla payload when the list was written.
                continue
            unfindable.append(f"{name} -> {source_name}")
        self.assertEqual(
            unfindable, [],
            "these invisible items' base art cannot be found in any searched "
            "location, so Base Graphics would omit them:\n  "
            + "\n  ".join(unfindable),
        )

    def test_the_vanilla_only_list_is_accurate_and_minimal(self):
        """The excuse list must not drift into a place to hide a real gap.

        An allow-list added to stop a check being too strict suppresses the
        signal in the other direction too, so it is asserted from BOTH sides
        whenever the payload is actually available: every pinned name must
        really be in the payload, and no pinned name may have since become
        available in a tracked directory, which would make its excuse
        unnecessary and mask a later removal.
        """
        payload_dirs = [
            Path(p) / "Images" / "Furniture"
            for p in patcher.VANILLA_RUNTIME_PAYLOAD_SOURCE_DIRS
        ]
        if not any(d.is_dir() for d in payload_dirs):
            self.skipTest("vanilla_runtime_payload is a gitignored build input")
        tracked = [
            ROOT / "patcher_assets" / "inherited_runtime_images" / "Furniture",
            patcher.NEW_FURNITURE_ART_DIR,
        ]
        for source_name in sorted(VANILLA_ONLY_BASE_SOURCES):
            with self.subTest(source_name):
                self.assertTrue(
                    any((d / source_name).is_file() for d in payload_dirs),
                    f"{source_name} is excused as vanilla-only but is not in "
                    + "the payload, so its excuse hides a missing source",
                )
                self.assertFalse(
                    any((d / source_name).is_file() for d in tracked),
                    f"{source_name} is now tracked, so it no longer needs "
                    + "the vanilla-only excuse; remove it from the list",
                )

    def test_a_source_that_is_neither_tracked_nor_pinned_is_not_excused(self):
        """A NEW item with no committed art must fail even on a fresh clone."""
        self.assertNotIn(
            "AnInventedSourceThatWasNeverCommitted.png", VANILLA_ONLY_BASE_SOURCES,
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


class BaseGraphicsPrefersTrackedArtOverASeedCopy(unittest.TestCase):
    """A stale copy in OUT must not win over the tracked source.

    This runs the real function against a real output tree rather than
    slicing the source, because the defect it guards is an ORDERING one and
    ordering is invisible to a text match.

    The old resolution asked whether OUT already had the base image and only
    looked further when it did not. A seeded build can inherit an older or
    corrupted copy, and because that file EXISTED the tracked source was never
    consulted -- so the Base Graphics folder snapshotted the stale bytes and
    handed them back when a player restored their visible art.
    Both restore_preserved_inherited_art() and install_new_furniture_art()
    correct the ACTIVE art, but both run after this function, so neither
    repairs the reference set.

    Note what is NOT sufficient as a test: deleting the seed copy. The
    clean-build case passes either way, because the tracked directory is on
    the fallback search path. Only a seed copy that exists and is WRONG
    separates the two behaviours, which is why this test corrupts rather than
    removes it.
    """

    def test_a_corrupt_seed_copy_does_not_reach_the_reference_set(self):
        import hashlib
        import os
        import shutil
        import tempfile

        tracked = ROOT / "patcher_assets" / "new_furniture_art" / "SpaLoungerStd.png"
        if not tracked.is_file():
            self.fail(f"tracked added art is missing: {tracked}")
        source = ROOT / "outputs" / "VF2-Mobile-Additive-Furniture-Pack"
        furniture = source / "Images" / "Furniture"
        if not furniture.is_dir():
            self.skipTest("no generated output tree; run the generator first")

        previous = os.environ.get("VF2_PATCH_OUT")
        temporary = tempfile.mkdtemp()
        try:
            out = Path(temporary) / "OUT"
            (out / "Images" / "Furniture").mkdir(parents=True)
            for entry in furniture.iterdir():
                if entry.is_file():
                    shutil.copy2(entry, out / "Images" / "Furniture" / entry.name)
            stale = out / "Images" / "Furniture" / "SpaLoungerStd.png"
            stale.write_bytes(b"\x89PNG\r\n\x1a\n" + b"stale seed copy" * 40)

            os.environ["VF2_PATCH_OUT"] = str(out)
            import importlib

            reloaded = importlib.reload(patcher)
            manifest = {}
            reloaded.sync_invisible_furniture_reference_sets(manifest)

            shipped = (
                out
                / "OptionalVisualMods"
                / "Invisible Furniture - Base Graphics"
                / "InvisibleSpaLounger.png"
            )
            self.assertTrue(
                shipped.is_file(),
                "the Spa Lounger is absent from the Base Graphics reference set",
            )
            self.assertEqual(
                hashlib.sha256(shipped.read_bytes()).hexdigest(),
                hashlib.sha256(tracked.read_bytes()).hexdigest(),
                "the reference set shipped the stale seed bytes instead of the "
                "tracked art, so restoring visible graphics gives back a bad image",
            )
        finally:
            if previous is None:
                os.environ.pop("VF2_PATCH_OUT", None)
            else:
                os.environ["VF2_PATCH_OUT"] = previous
            shutil.rmtree(temporary, ignore_errors=True)
            import importlib

            importlib.reload(patcher)


if __name__ == "__main__":
    unittest.main()
