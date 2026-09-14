#!/usr/bin/env python3
"""The patched executables must not change save-folder handling.

THE OWNER'S INSTRUCTION, recorded verbatim because it names a consequence
rather than a preference:

    "MAKE SURE THE MODIFIED EXES DO NOT HARDCODE ANY SPECIFIC SAVE FOLDER
    NAMES. THAT FUNCTIONALITY SHOULD BE ENTIRELY IDENTICAL TO BASE-GAME
    BEHAVIOR. CHANGING ANY PART OF IT WILL CAUSE UNNECESSARY BUGS AND CRASHES
    AND IT ALREADY HAS IN THE PAST!"

So this is not a style rule. A save path that differs from the stock game
sends a player's saves somewhere the base game will not look, and the failure
shows up as lost progress rather than as a crash at the patch site.

WHAT THIS CHECKS, AND WHY IT IS A COMPARISON RATHER THAN A BLACKLIST.
Asserting "the patched exe contains no path strings" would be wrong: the
stock game legitimately contains several, and a patched build must keep them.
The property that matters is SAMENESS -- the patched image carries exactly
the path strings the stock image does, no more and no fewer. A blacklist
would fail on the stock strings; a whitelist would pass a build that dropped
one. Counting both sides catches an addition AND a deletion.

The generator is checked too, since a hardcoded path introduced there would
reach every variant at once.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
OUTPUTS = ROOT / "outputs"

# Strings that would indicate save-location handling. Deliberately broad:
# a false positive costs one investigation, a false negative costs saves.
SAVE_PATH_MARKERS = (
    b"My Games",
    b"SavedGames",
    b"Saved Games",
    b"Last Day of Work",
    b"Documents",
    b"AppData",
    b"LOCALAPPDATA",
)


def _newest_matrix_exe(pattern):
    """The newest matrix build's exe matching a variant name fragment."""
    if not OUTPUTS.is_dir():
        return None
    candidates = sorted(
        (p for p in OUTPUTS.glob("VF2-B*-matrix-*%s/*.exe" % pattern)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


class TheGeneratorAddsNoSavePath(unittest.TestCase):
    def test_no_save_folder_literal_is_written_into_the_patch(self):
        """A path literal in the generator would reach every variant.

        Comments are stripped: this file and the ledger discuss these names
        at length, and a substring search over raw source would match the
        prose explaining the rule rather than any emitted string.
        """
        source = GENERATOR.read_text(encoding="utf-8", errors="replace")
        code = "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("#")
        )
        # Only C string literals reach the patched image. Python-side names
        # like CCollectableItem::SaveState are engine symbols, not paths.
        literals = re.findall(r'"([^"\n]{4,120})"', code)
        # A marker alone is not a path. "Last Day of Work Poster" is a store
        # item and "You bought a Last Day of Work poster." is its message --
        # both contain the studio name and neither goes near a save folder.
        # Requiring a path SEPARATOR alongside the marker is what separates a
        # location from a product name. Without this the check fires on two
        # shop strings and would have been silenced rather than narrowed,
        # which is how a guard ends up asserting nothing.
        def looks_like_a_path(lit):
            if not any(m.decode("ascii") in lit for m in SAVE_PATH_MARKERS):
                return False
            return "\\" in lit or "/" in lit or lit.endswith(":")

        offenders = [lit for lit in literals if looks_like_a_path(lit)]
        self.assertEqual(
            offenders, [],
            "the generator emits a save-path literal, which would change save "
            "handling in every variant: %s" % offenders[:4])


class ThePatchedImageMatchesTheStockImage(unittest.TestCase):
    """Compare a patched build against the stock build it was seeded from."""

    def setUp(self):
        self.patched = _newest_matrix_exe("final_all_enabled")
        if self.patched is None:
            self.skipTest("no matrix build present to compare")
        self.stock = ROOT / "outputs" / "VF2-B185-Release" / "payload"
        stock_exes = sorted(self.stock.glob("*Final All-Enabled*.exe")) \
            if self.stock.is_dir() else []
        if not stock_exes:
            self.skipTest("the stock B185 payload is not unpacked here")
        self.stock_exe = stock_exes[0]

    def test_save_path_strings_are_unchanged(self):
        patched = self.patched.read_bytes()
        stock = self.stock_exe.read_bytes()
        for marker in SAVE_PATH_MARKERS:
            with self.subTest(marker=marker.decode("ascii")):
                self.assertEqual(
                    patched.count(marker), stock.count(marker),
                    "%s appears %d times in the patched image and %d in the "
                    "stock one; save handling must be byte-identical to the "
                    "base game"
                    % (marker.decode("ascii"),
                       patched.count(marker), stock.count(marker)))


if __name__ == "__main__":
    unittest.main()
