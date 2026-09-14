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
stock game legitimately contains one, and a patched build must keep it. The
property that matters is SAMENESS -- the patched image resolves saves from
exactly the path strings the stock image does, no more and no fewer. A
blacklist would fail on the stock string; a whitelist would pass a build that
dropped it. Comparing the two sets catches an addition AND a deletion.

THE BASELINE IS THE VANILLA EXE, NOT A RELEASE PAYLOAD.
work/vanilla_runtime_payload/Virtual Families 2.exe is the verified stock
game. The release payload's "Final All-Enabled Native" executable is NOT a
baseline: export_offline_patch_bundle.py copies the patched
final_playtest_native_exe into the payload under that label, so comparing
against it compares a build with a packaged copy of itself and would accept a
regression already present in the previous release.

The difference is measurable rather than theoretical. Against the true
vanilla image the marker "Last Day of Work" appears once (the copyright
string); in every patched build it appears three times, because the mod adds
the "Last Day of Work Poster" furniture item and its achievement text. A
check that compares patched against patched sees 3 == 3 and reports
agreement while telling you nothing about save paths.

WHY DECODED STRINGS RATHER THAN MARKER COUNTS.
Counting occurrences of marker byte sequences does not establish that the
path strings are unchanged, in either direction:

  * it counts things that are not paths -- "Last Day of Work Poster" is a
    store item, and the one "Documents" hit in the stock image is
    eString_ShreddingDocuments, an activity name;
  * it is blind to a substitution that preserves the count. Rewriting the
    save root from \\LDW to \\XYZ, or to Documents\\Other, can leave every
    marker count identical.

So this decodes complete ASCII and UTF-16LE strings from both images and
compares the path VALUES.

MEASURED: across all 160 built executables in outputs/ (B178 through B185),
every variant carries exactly the stock set, and the only save-path string
the game has is "\\LDW" -- which sits in the image beside "\\images\\",
"\\sounds\\", "\\assets\\" and the "%s%d.ldw" save-file format, i.e. the
save-path machinery itself.

VERIFIED AGAINST KNOWN-BADS. Each of these is detected: adding C:\\VF2Saves;
adding Documents\\LDW\\Virtual Families 2; swapping \\LDW for \\XYZ (the
count-preserving case above); and adding a UTF-16 "My Games\\VF2".

The generator is checked too, since a hardcoded path introduced there would
reach every variant at once.
"""
import os
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
OUTPUTS = ROOT / "outputs"
VANILLA_EXE = ROOT / "work" / "vanilla_runtime_payload" / "Virtual Families 2.exe"

BACKSLASH = chr(92)

# Names that would indicate save-location handling. Deliberately broad: a
# false positive costs one investigation, a false negative costs saves.
SAVE_PATH_MARKERS = (
    "My Games",
    "SavedGames",
    "Saved Games",
    "Last Day of Work",
    "Documents",
    "AppData",
    "LOCALAPPDATA",
    "APPDATA",
    "USERPROFILE",
    "LDW",
    "ldw",
)

# A drive-absolute or UNC path is a hardcoded location whatever it is named,
# so it counts even without a marker -- "C:\VF2Saves" contains none of the
# names above. The trailing run is required because compiled code is full of
# byte pairs that decode as "\\Q" or "X:\", which are opcodes and not paths.
ABSOLUTE_PATH = re.compile(
    r"^(?:[A-Za-z]:[" + re.escape(BACKSLASH) + r"/]"
    r"|" + re.escape(BACKSLASH * 2) + r"[A-Za-z0-9_.-]{2,})"
    r"[A-Za-z0-9_. -]{2,}[" + re.escape(BACKSLASH) + r"/]?")

# Asset references are relative resource names, not save locations. The mod
# legitimately adds several (the LDW poster art is "Furniture/LDWPoster1Std.png",
# which carries the studio name without going near a save folder).
ASSET_PREFIXES = ("Furniture/", "Images/", "Assets/", "Sounds/")
ASSET_SUFFIXES = (".png", ".jpg", ".bmp", ".swf", ".wav", ".ogg", ".mp3")


def _decoded_strings(data, minlen=3):
    """Every printable ASCII and UTF-16LE string in an image."""
    found = []
    for match in re.finditer(rb"[\x20-\x7e]{%d,300}" % minlen, data):
        found.append(match.group().decode("ascii"))
    for match in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,300}" % minlen, data):
        found.append(match.group().decode("utf-16-le"))
    return found


def save_path_strings(data):
    """The complete path strings in an image that could locate a save folder."""
    found = set()
    for text in _decoded_strings(data):
        named = (any(marker in text for marker in SAVE_PATH_MARKERS)
                 and (BACKSLASH in text or "/" in text or text.endswith(":")))
        if not (named or ABSOLUTE_PATH.match(text)):
            continue
        if any(prefix in text for prefix in ASSET_PREFIXES):
            continue
        if text.lower().endswith(ASSET_SUFFIXES):
            continue
        found.add(text)
    return found


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
        # Scoped to marker-plus-separator rather than reusing the image
        # scan's absolute-path rule: this is Python source, not the emitted
        # image, and it legitimately contains build-HOST paths that never
        # reach the player -- "C:/Users/Owner" appears inside the guard that
        # rejects a leaked build path, and r"C:\Windows" is the WinSxS
        # lookup default. Flagging those would be flagging the check itself.
        def looks_like_a_path(lit):
            if not any(marker in lit for marker in SAVE_PATH_MARKERS
                       if marker not in ("LDW", "ldw")):
                return False
            return BACKSLASH in lit or "/" in lit or lit.endswith(":")

        offenders = sorted(lit for lit in literals if looks_like_a_path(lit))
        self.assertEqual(
            offenders, [],
            "the generator emits a save-path literal, which would change save "
            "handling in every variant: %s" % offenders[:4])


class ThePatchedImageMatchesTheStockImage(unittest.TestCase):
    """Compare a patched build against the verified vanilla executable."""

    def setUp(self):
        # work/vanilla_runtime_payload is a build prerequisite -- build_matrix.ps1
        # refuses to run without it -- so its absence means this clone cannot
        # build either, and the check is skipped rather than failed. When a
        # matrix build IS present the comparison is mandatory: skipping it
        # then would be the "green suite over an unverified artifact" this
        # repository keeps producing.
        self.patched = _newest_matrix_exe("final_all_enabled")
        if self.patched is None:
            if os.environ.get("VF2_REQUIRE_SAVE_PATH_CHECK") == "1":
                self.fail(
                    "VF2_REQUIRE_SAVE_PATH_CHECK=1 but no matrix build is "
                    "present in outputs/ to compare against vanilla")
            self.skipTest(
                "no matrix build present to compare (set "
                "VF2_REQUIRE_SAVE_PATH_CHECK=1 to make this a failure, as a "
                "post-build release gate should)")
        if not VANILLA_EXE.is_file():
            self.skipTest(
                "work/vanilla_runtime_payload is not populated in this clone, "
                "so there is no verified stock image to compare against")

    def test_save_path_strings_are_unchanged(self):
        patched = save_path_strings(self.patched.read_bytes())
        stock = save_path_strings(VANILLA_EXE.read_bytes())

        added = sorted(patched - stock)
        self.assertEqual(
            added, [],
            "%s introduces save-path strings the stock game does not have, "
            "which would send saves where the base game will not look: %s"
            % (self.patched.name, added))

        dropped = sorted(stock - patched)
        self.assertEqual(
            dropped, [],
            "%s is missing save-path strings the stock game has, which would "
            "change where saves are read from: %s"
            % (self.patched.name, dropped))


if __name__ == "__main__":
    unittest.main()
