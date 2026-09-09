#!/usr/bin/env python3
"""The hairstyle icons must not be clipped in the BUILT assets.

The owner reported the store icons were cut off. They were being cropped on the
engine's own 28x56 indexing cell, but the drawn heads are about 29px wide and
centred on 12 visual frames of 56x56, so a 28px cut sliced every head in half.

This reads the built PNGs rather than the generator, because that is where the
defect was visible and where a regression would land. B179 shipped 100 icons at
28x56 whose opaque pixels ran to column 0 -- touching the edge is the signature
of a clipped head. B180 ships them at 56x56 with the head floating clear of
both edges.

Skips when no build output is present, so a clean checkout is not red.
"""
import glob
import os
import struct
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"


def _png_size(path):
    data = Path(path).read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _current_release_prefix():
    """The newest release that actually linked something.

    NOT a hardcoded release name. This suite was pinned to "B180", which is no
    longer produced, so both of its checks skipped -- silently, for every
    release after B180. Measured when that was found: 128 HairstyleIcons
    directories present, 0 matching B180 with a linked exe, 32 matching the
    current release with 100 icons each. Roughly 3,200 shipped icons verified
    by nothing.

    The identical defect had already been found and fixed in
    test_shipped_lounger_fmaps.py; it simply was not swept for elsewhere.

    VF2_VERIFY_RELEASE names a release explicitly. Otherwise the newest one
    with a linked exe wins -- a build_matrix run that dies before linking still
    leaves a directory behind, so "newest directory" is not the same question
    as "newest release".
    """
    named = os.environ.get("VF2_VERIFY_RELEASE")
    if named:
        return "VF2-%s-matrix-" % named
    best = None
    for d in OUTPUTS.glob("VF2-B*-matrix-*"):
        if d.name.endswith("-logs") or not d.is_dir():
            continue
        if not list(d.glob("*.exe")):
            continue
        prefix = d.name.rsplit("-", 1)[0] if "-" in d.name else d.name
        # RELEASE IDS ARE NOT ALWAYS INTEGERS. B174.1 and B174b are both real
        # forms -- data/vf2 carries release-identities-B174.1.json today. A
        # bare int() raises on those and the except-continue DISCARDED them
        # silently, so the helper would fall back to an older release, or to
        # None and skip everything, exactly when a point release was newest.
        # That is the same silent-skip shape this whole suite exists to close.
        #
        # Sorted as (integer part, suffix) so B174 < B174.1 < B174b < B185
        # without pretending the suffix is a number.
        try:
            token = d.name.split("-")[1].lstrip("B")
        except IndexError:
            continue
        head = ""
        for ch in token:
            if not ch.isdigit():
                break
            head += ch
        if not head:
            continue
        key = (int(head), token[len(head):])
        if best is None or key > best[0]:
            best = (key, prefix)
    return best[1] + "-" if best else None


def _icon_dirs():
    return sorted(OUTPUTS.glob("VF2-*-matrix-*/Images/HairstyleIcons"))


class TestShippedHairstyleIconsAreNotClipped(unittest.TestCase):
    def setUp(self):
        # Only finished variants. A matrix build seeds each variant folder from
        # the previous release before regenerating it, so a variant that has
        # not linked yet still holds the PREVIOUS release's assets. Checking
        # those reports the old defect against the new build -- which is
        # exactly what happened the first time this test ran.
        prefix = _current_release_prefix()
        self.dirs = [
            d for d in _icon_dirs()
            if prefix and d.parts[-3].startswith(prefix)
            and list(d.parents[1].glob("*.exe"))
        ]
        if not self.dirs:
            # AN EXPLICIT REQUEST THAT CANNOT BE HONOURED IS A FAILURE, NOT A
            # SKIP. Setting VF2_VERIFY_RELEASE asks for one named release to
            # be verified; if a typo or cleaned output means nothing matches,
            # unittest would otherwise report OK (skipped=2) and the person
            # who asked would believe that release had been checked. Absence
            # of an unnamed current release is a genuine prerequisite and
            # still skips.
            named = os.environ.get("VF2_VERIFY_RELEASE")
            if named:
                self.fail(
                    "VF2_VERIFY_RELEASE=%s was requested but no finished "
                    "variant with hairstyle icons matches %s -- check the "
                    "name, or that the outputs have not been cleaned"
                    % (named, prefix)
                )
            self.skipTest(
                "no finished %s variant with hairstyle icons"
                % (prefix or "current-release")
            )

    def test_every_icon_is_a_full_visual_frame(self):
        expected = patcher.HEAD_STORE_ICON_CELL_SIZE
        # Guard the premise: the icon cell must not be the engine cell, or the
        # whole point of the fix is gone and this test would pass vacuously.
        self.assertNotEqual(expected, patcher.HEAD_STORE_CELL_SIZE)
        for d in self.dirs:
            icons = sorted(glob.glob(str(d / "*.png")))
            self.assertTrue(icons, f"{d} has no icons")
            for icon in icons:
                with self.subTest(icon=Path(icon).name, build=d.parts[-3]):
                    self.assertEqual(_png_size(icon), expected)

    def test_no_head_touches_a_side_edge(self):
        """Touching a side edge is the signature of the clipped crop.

        B179's icons ran to column 0. A head cut at the frame boundary always
        reaches the edge it was cut at, so this catches the regression even if
        the canvas size were restored without fixing the crop offset.
        """
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not available")
        for d in self.dirs:
            for icon in sorted(glob.glob(str(d / "*.png"))):
                with self.subTest(icon=Path(icon).name):
                    image = Image.open(icon).convert("RGBA")
                    width, height = image.size
                    pixels = image.load()
                    cols = [
                        x for x in range(width)
                        if any(pixels[x, y][3] > 8 for y in range(height))
                    ]
                    self.assertTrue(cols, f"{icon} is fully transparent")
                    self.assertNotEqual(
                        min(cols), 0,
                        f"{Path(icon).name}: opaque pixels reach the left edge, "
                        "which is what a clipped head looks like",
                    )
                    self.assertNotEqual(
                        max(cols), width - 1,
                        f"{Path(icon).name}: opaque pixels reach the right edge",
                    )


if __name__ == "__main__":
    unittest.main()
