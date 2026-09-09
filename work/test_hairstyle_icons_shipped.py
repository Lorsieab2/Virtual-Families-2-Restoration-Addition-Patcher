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


def _release_sort_key(identifier):
    """Order B174 < B174.1 < B174b < B185, or None if unparseable.

    Releases are not plain integers on this project: B174.1 and B174b are both
    real forms. int() raises on either, and an except-continue around it drops
    the release entirely -- which is how the newest build can be silently
    discarded in favour of an older one.
    """
    text = identifier.lstrip("B")
    head = ""
    for ch in text:
        if ch.isdigit():
            head += ch
        else:
            break
    if not head:
        return None
    return (int(head), text[len(head):])


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

    POINT AND LETTER RELEASES COUNT. B174.1 exists (see
    data/vf2/release-identities-B174.1.json), and an int() conversion raises on
    it. An earlier version of this function swallowed that with `continue`, so
    the newest release could be silently discarded and an older one chosen --
    landing straight back in the skip this function was written to remove.
    """
    named = os.environ.get("VF2_VERIFY_RELEASE")
    if named:
        prefix = "VF2-%s-matrix-" % named
        # AN EXPLICITLY NAMED RELEASE THAT DOES NOT EXIST IS A MISTAKE, NOT A
        # PREREQUISITE. Returning an unmatched prefix makes setUp skip, so a
        # typo or a cleaned-away release reports OK (skipped=2) to someone who
        # deliberately asked to verify something. Same distinction as a missing
        # toolchain skipping while a missing contract fails.
        if not any(d.is_dir() and not d.name.endswith("-logs")
                   for d in OUTPUTS.glob(prefix + "*")):
            raise AssertionError(
                "VF2_VERIFY_RELEASE=%s names a release with no matrix output "
                "under %s; nothing would be verified. Check the name, or "
                "unset it to use the newest linked release." % (named, OUTPUTS))
        return prefix
    best = None
    unparsed = []
    for d in OUTPUTS.glob("VF2-B*-matrix-*"):
        if d.name.endswith("-logs") or not d.is_dir():
            continue
        if not list(d.glob("*.exe")):
            continue
        prefix = d.name.rsplit("-", 1)[0] if "-" in d.name else d.name
        parts = d.name.split("-")
        if len(parts) < 2:
            unparsed.append(d.name)
            continue
        key = _release_sort_key(parts[1])
        if key is None:
            unparsed.append(d.name)
            continue
        if best is None or key > best[0]:
            best = (key, prefix)
    if unparsed and best is None:
        raise AssertionError(
            "no release identifier could be parsed from %s; the newest release "
            "cannot be determined and these checks would skip while shipped "
            "icons went unverified" % sorted(unparsed)[:6])
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
