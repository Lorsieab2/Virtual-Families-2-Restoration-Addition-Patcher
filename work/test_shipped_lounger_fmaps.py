#!/usr/bin/env python3
"""The loungers' placement maps must be desktop-safe in the BUILT assets.

test_borrowed_fmaps_are_desktop_safe.py checks the selection logic against the
source tree. This checks what actually reached a build, because the defect it
guards against shipped in B179 despite the source naming the right donor: the
patch installed the desktop-safe map over each donor's OWN name, and a
borrower's copy is written under the BORROWER's name, which that pass never
visited.

What B179 shipped, and what B180 must not:

    Chaise_brown.png.fmap          no non-zero cells        (desktop-safe)
    InvisibleSpaLounger.png.fmap   0x01B00000 x111, 0x01B00001 x31,
                                   0x01B09800 x1            (RAW MOBILE)

The operative cell is the peep-slot anchor. The behavior ledger records that it
must be translated from mobile 0x01B09800 to desktop 0x00009800, and that
without the translated anchor the desktop FindPeepSlot path rejects every
chair -- which is exactly the reported symptom of a villager lying in the wrong
position or changing behaviour the moment it sat down.

Skips when no finished build is present, so a clean checkout is not red.
"""
import hashlib
import os
import re
import struct
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"

DESKTOP_ANCHOR = 0x00009800
MOBILE_ANCHOR = 0x01B09800

# The desktop-safe map for the donor these all borrow. Comparing against the
# real thing beats inventing a numeric threshold: a first attempt treated
# anything >= 0x01000000 as a mobile marker and flagged 0x2000A800, which is a
# perfectly ordinary DESKTOP cell present in the safe map itself.
PC_FMAP_DONOR = (
    ROOT / "patcher_assets" / "optional_patches" /
    "mobile_furniture_behaviors" / "pc_fmaps" / "Chaise_brown.png.fmap"
)

# The RAW donor, whose geometry #201 exists to carry into a borrower. The
# desktop-safe map above is deliberately sparse -- 12 occupied cells against
# this one's 154 -- and a borrower given only that has almost no collision
# area: the Patio Table borrower measured 241 occupied cells down to 8. So a
# borrower is the raw geometry with the safe map's translated cells laid over
# it, and BOTH halves need pinning. The safe half is checked above; without
# this one nothing notices if the geometry silently stops arriving.
RAW_FMAP_DONOR = (
    ROOT / "patcher_assets" / "optional_patches" /
    "mobile_furniture_behaviors" / "mobile_fmaps" / "Chaise_brown.png.fmap"
)

# THE UNTRANSLATED PEEP-SLOT ANCHOR ALONE. That is the cell which actually
# breaks placement, and it is the only mobile value this patcher translates:
# desktop_safe_fmap_source's docstring states the mechanism -- "without the
# translated anchor FindPeepSlot rejects every chair. That is why a villager
# dropped on a Spa Lounger lay in the wrong position" -- and the generator
# records exactly one translation, "translated_mobile_peep_slot_marker",
# mobile 0x01b09800 -> desktop 0x00009800. No translation record, validator or
# ledger entry exists for any other mobile value.
#
# 0x01B00000 and 0x01B00001 WERE listed here. They are footprint GEOMETRY, not
# placement metadata, and listing them made this suite fail a build that #201
# deliberately produces. #201 gives a borrower the donor's full collision
# geometry because the desktop-safe map is too sparse to stand alone -- the
# Patio Table borrower measured 241 occupied cells down to 8 without it.
# Stripping those cells to satisfy this list would cost the loungers their
# collision area, which is the "the hotspot for the spa loungers are very
# small" complaint this work exists to fix. The owner's decision was to ship
# the geometry.
#
# WHAT IS NOT ESTABLISHED, and why the anchor stays forbidden rather than the
# check being deleted: nobody has disassembled how the desktop collision lookup
# interprets a non-anchor cell. The evidence that the footprint values are
# tolerated is that B179 -- a shipped, playable build -- installed a lounger
# map carrying all three, anchor included, with no lying-position report in a
# ledger that records lounger behaviour in detail. That is tolerance observed
# in one build, not proof from the engine's code. If a villager is ever seen
# lying wrong on a spa lounger, this is the first place to look.
FORBIDDEN_MOBILE_CELLS = (0x01B09800,)

LOUNGERS = (
    "InvisibleSpaLounger.png.fmap",
    "InvisibleLounger.png.fmap",
    "SpaLoungerStd.png.fmap",
)

# The two spa loungers ship a DELIBERATELY WIDER drop target than the chaise
# they borrow: the donor's object cells are an eleven-cell ragged diagonal and
# dropping a villager on it was reported as very difficult. The generator
# dilates their own copies by one cell, so they are no longer byte-identical to
# the donor and no longer identical to the plain Invisible Lounger.
#
# That is the intended difference, and it is narrow: only the object-cell count
# may change. Every other property this file checks -- no mobile-only markers,
# no untranslated anchor, same grid, same header -- still applies to all three.
WIDENED_LOUNGERS = (
    "InvisibleSpaLounger.png.fmap",
    "SpaLoungerStd.png.fmap",
)


def _cell_list(path):
    """The map's cells IN ORDER, one entry per cell.

    _cells() summarises to a Counter, which answers "how many of each value"
    and cannot answer "what is at cell N" or even "how many cells are there".
    Any check about positions, sizes or occupancy counts needs this instead --
    iterating the Counter yields each distinct value once, which silently turns
    a 266-cell map into a 3-element sequence.
    """
    data = path.read_bytes()
    count = (len(data) - 0x20 - 0x10) // 4
    return [
        struct.unpack_from("<I", data, 0x20 + 4 * i)[0] for i in range(count)
    ]


def _cells(path):
    return Counter(_cell_list(path))


def _release_glob():
    """Which release's matrix output to verify.

    This was pinned to "VF2-B180-matrix-*". That folder is no longer produced,
    so every check in this file skipped -- silently, and for every release
    after B180. The suite reported "5 skipped" and read as green while
    verifying nothing at all, which is the failure this file exists to prevent:
    a check that cannot fail is not evidence.

    VF2_VERIFY_RELEASE names the release explicitly. Otherwise the NEWEST
    matrix output present is used, so the checks follow the current release
    instead of a frozen one.
    """
    named = os.environ.get("VF2_VERIFY_RELEASE")
    if named:
        return "VF2-%s-matrix-*" % named
    # ONLY RELEASES THAT ACTUALLY LINKED SOMETHING COUNT.
    #
    # build_matrix.ps1 creates its log root BEFORE building any variant, so a
    # run that dies before linking still leaves VF2-B<n>-matrix-<date>-logs in
    # outputs/. Counting that as a release makes max() prefer the broken run
    # over the completed one; _finished_builds() then filters the logs
    # directory out, yields nothing, and every check skips -- OK (skipped=5)
    # while a complete release sat there unverified.
    #
    # A release qualifies only if at least one of its variant directories has
    # a linked exe and an Assets directory, which is the same test
    # _finished_builds() applies.
    releases = set()
    for d in OUTPUTS.glob("VF2-B*-matrix-*"):
        if d.name.endswith("-logs"):
            continue
        m = re.match(RELEASE_NAME_RE, d.name)
        if not m:
            continue
        if list(d.glob("*.exe")) and (d / "Assets").is_dir():
            releases.add(m.group(1))
    if not releases:
        return None
    return "VF2-%s-matrix-*" % max(releases, key=_release_sort_key)


# Releases are not always plain integers. data/vf2 already carries
# build-matrix-release-b174.1.json, -b174.2.json and -b174b.json, so a pattern
# demanding "-matrix-" straight after the digits skips every point release --
# either verifying an older base release or, when a point release is newest,
# returning nothing and skipping every check in this file. That is the same
# silent-skip failure this change exists to remove, so the full naming
# convention is parsed: B<major>, optionally .<minor>, optionally a letter.
RELEASE_NAME_RE = r"VF2-(B\d+(?:\.\d+)?[a-z]?)-matrix-"


def _release_sort_key(name):
    """Order B174 < B174.1 < B174.2 < B174b < B181 < B184.

    Plain-string ordering puts B181 before B84 and B174.10 before B174.2, so
    each component is compared as its own type: the major as an integer, the
    minor as an integer (absent sorts first), the letter suffix as text.
    """
    m = re.fullmatch(r"B(\d+)(?:\.(\d+))?([a-z]?)", name)
    if not m:
        return (0, 0, "")
    major, minor, suffix = m.groups()
    return (int(major), int(minor) if minor else 0, suffix)


# The spa-lounger hotspot widening merged in #239, after the B181 matrix was
# built. A build from B181 or earlier cannot carry it, and demanding it there
# would be asserting a fix onto a release that predates it.
WIDENING_FIRST_RELEASE = (182, 0, "")


def _release_has_widening(build_name):
    m = re.match(RELEASE_NAME_RE, build_name)
    if not m:
        return False
    return _release_sort_key(m.group(1)) >= WIDENING_FIRST_RELEASE


def _finished_builds():
    """Variant folders that actually linked, for the current release only.

    A matrix build seeds each variant from the previous release before
    rebuilding it, so an unlinked folder still holds the PREVIOUS release's
    maps -- and would report B179's defect against B180.
    """
    pattern = _release_glob()
    if pattern is None:
        return
    for d in sorted(OUTPUTS.glob(pattern)):
        if d.name.endswith("-logs"):
            continue
        if list(d.glob("*.exe")) and (d / "Assets").is_dir():
            yield d


def _refuse_or_skip(case):
    """AN EXPLICIT REQUEST THAT MATCHES NOTHING IS AN ERROR, NOT A SKIP.

    Setting VF2_VERIFY_RELEASE asks for a named release to be verified. If it
    is misspelled, or names output that has since been cleaned up, skipping
    reports the same "OK" as a real verification -- VF2_VERIFY_RELEASE=B999
    gave OK (skipped=5). That is the silent skip this file exists to remove,
    reintroduced through the escape hatch added to remove it.

    With the variable unset there is nothing to be wrong about: a clean
    checkout has no build output and must not be red.

    Shared by both test classes deliberately. The first version of this guard
    lived in one setUp, and the other class kept skipping -- so the same
    request still produced a skip, just a quieter one.
    """
    named = os.environ.get("VF2_VERIFY_RELEASE")
    if named:
        case.fail(
            "VF2_VERIFY_RELEASE=%s was requested but no finished build matches "
            "%r under %s. Verification of a named release cannot pass by being "
            "skipped." % (named, _release_glob(), OUTPUTS)
        )
    case.skipTest("no finished current-release build output")


class TestShippedLoungerMapsAreDesktopSafe(unittest.TestCase):
    def setUp(self):
        self.builds = list(_finished_builds())
        if not self.builds:
            _refuse_or_skip(self)

    def test_no_lounger_carries_the_untranslated_mobile_anchor(self):
        for build in self.builds:
            for name in LOUNGERS:
                path = build / "Assets" / name
                if not path.is_file():
                    continue
                with self.subTest(build=build.name, fmap=name):
                    cells = _cells(path)
                    self.assertNotIn(
                        MOBILE_ANCHOR, cells,
                        "carries the untranslated mobile peep anchor; the "
                        "desktop FindPeepSlot path rejects every chair with "
                        "this, which is the wrong-lying-position bug",
                    )
                    self.assertIn(
                        DESKTOP_ANCHOR, cells,
                        "is missing the desktop peep anchor entirely",
                    )

    def test_no_lounger_carries_mobile_only_footprint_markers(self):
        for build in self.builds:
            for name in LOUNGERS:
                path = build / "Assets" / name
                if not path.is_file():
                    continue
                with self.subTest(build=build.name, fmap=name):
                    cells = _cells(path)
                    found = sorted(
                        c for c in FORBIDDEN_MOBILE_CELLS if c in cells
                    )
                    self.assertEqual(
                        found, [],
                        f"mobile-only markers {[hex(m) for m in found]} "
                        "reached the desktop content map",
                    )

    def test_the_shipped_map_carries_the_desktop_safe_translated_cells(self):
        """Every cell the desktop-safe map REWRITES must reach the borrower.

        This asserted byte-identity to the desktop-safe donor, which #201 made
        impossible on purpose. #201 gives a borrower the donor's full collision
        geometry -- the desktop-safe map is deliberately sparse and a borrower
        has no map of its own, so on its own it leaves almost no collision
        area: the Patio Table borrower measured 241 occupied cells down to 8.
        A borrower therefore carries the donor's geometry PLUS the safe map's
        translated cells, and can never be identical to the safe map alone.

        What still has to hold, and is what this now checks, is the half that
        keeps placement working: every cell the desktop-safe map rewrote must
        appear in the shipped map with the desktop value. That is where the
        anchor lives, so an untranslated anchor still fails here as well as in
        the marker check above.
        """
        if not PC_FMAP_DONOR.is_file():
            self.skipTest("pc_fmaps donor is not present in this tree")
        expected = _cells(PC_FMAP_DONOR)
        for build in self.builds:
            for name in LOUNGERS:
                path = build / "Assets" / name
                if not path.is_file():
                    continue
                with self.subTest(build=build.name, fmap=name):
                    shipped_all = _cell_list(path)
                    safe_all = _cell_list(PC_FMAP_DONOR)
                    self.assertEqual(
                        len(shipped_all), len(safe_all),
                        "the shipped map is a different size from the "
                        "desktop-safe donor",
                    )
                    for index, safe in enumerate(safe_all):
                        if not safe:
                            continue
                        self.assertEqual(
                            shipped_all[index], safe,
                            "cell %d carries %#x but the desktop-safe map "
                            "rewrote it to %#x; a translated cell was lost"
                            % (index, shipped_all[index], safe),
                        )
                    # AND THE DONOR'S GEOMETRY MUST HAVE ARRIVED.
                    #
                    # The loop above skips every ZERO in the sparse safe map,
                    # which is exactly where the donor's geometry lives, so it
                    # cannot see that geometry going missing. #201 exists to
                    # carry those cells; nothing else in this file pins them,
                    # and the stock-donor borrower test names no lounger. A
                    # regression that reverted borrowers to the sparse map
                    # would pass every other check here.
                    #
                    # A widened cell legitimately replaces a donor cell, so
                    # the object value is allowed as a substitute.
                    # Gated on the release, exactly as the widening check is:
                    # #201 merged 2026-09-06, AFTER B181 was built, so a
                    # B181-or-earlier borrower legitimately carries only the
                    # sparse map and demanding the geometry there would assert
                    # a change onto a release that predates it.
                    if (_release_has_widening(build.name)
                            and RAW_FMAP_DONOR.is_file()):
                        raw_all = _cell_list(RAW_FMAP_DONOR)
                        if len(raw_all) == len(shipped_all):
                            kept = sum(
                                1 for raw, safe, now in zip(
                                    raw_all, safe_all, shipped_all)
                                if raw and not safe and now
                            )
                            carried = sum(
                                1 for raw, safe in zip(raw_all, safe_all)
                                if raw and not safe
                            )
                            self.assertEqual(
                                kept, carried,
                                "%d of %d donor geometry cells did not reach "
                                "the borrower; the sparse desktop-safe map "
                                "alone leaves it with almost no collision "
                                "area" % (carried - kept, carried),
                            )
                    if name not in WIDENED_LOUNGERS:
                        continue
                    shipped = _cells(path)
                    # ORDERED CELL LISTS FROM HERE DOWN.
                    #
                    # _cells() returns a Counter, which is right for the
                    # equality check above and wrong for everything below it.
                    # Iterating a Counter yields each distinct KEY once, so
                    # `len()` was the number of distinct values rather than the
                    # map size, `zip(expected, shipped)` walked keys instead of
                    # cells, and the per-value tally below counted every value
                    # exactly once -- which made `obj` an arbitrary pick rather
                    # than the object value, and left the widening assertion
                    # comparing 1 against 1 however much wider the map got.
                    #
                    # The result was a check that went red on a CORRECTLY
                    # widened artifact. Positions matter here, so the ordered
                    # lists are used.
                    shipped_cells = _cell_list(path)
                    expected_cells = _cell_list(PC_FMAP_DONOR)
                    self.assertEqual(
                        len(shipped_cells), len(expected_cells),
                        "the widened map changed size",
                    )
                    counts = Counter(v for v in expected_cells if v)
                    self.assertTrue(counts, "the donor map has no object cells")
                    obj = counts.most_common(1)[0][0]
                    # A CELL THE SAFE MAP REWROTE MAY NEVER BE OVERWRITTEN.
                    #
                    # This used to also require that every DIFFERING cell hold
                    # the object value, which assumed the borrower is the safe
                    # map plus dilation. #201 made that false on purpose: a
                    # borrower carries the DONOR'S GEOMETRY in cells the safe
                    # map leaves empty, because the safe map alone is too
                    # sparse to give a borrower any collision area -- the Patio
                    # Table borrower measured 241 occupied cells down to 8.
                    # Those donor cells are mobile-valued and legitimately not
                    # the object value.
                    #
                    # What must still hold is the half that keeps placement
                    # working: a cell the safe map rewrote -- the anchor and
                    # the object cells -- must survive untouched.
                    for index, (was, now) in enumerate(
                        zip(expected_cells, shipped_cells)
                    ):
                        if was == now or not was:
                            continue
                        self.fail(
                            "cell %d was rewritten from %#x to %#x; a cell "
                            "the desktop-safe map translated must survive"
                            % (index, was, now),
                        )
                    # The widening merged after B181 was built, so asserting it
                    # against B181 or earlier would assert a property onto a
                    # release that predates the fix. Every OTHER check in this
                    # method still applies to those builds: no mobile markers,
                    # no untranslated anchor, no overwritten cell.
                    if not _release_has_widening(build.name):
                        continue
                    # COUNT OCCURRENCES, NOT DISTINCT VALUES.
                    #
                    # _cells() returns a Counter, and iterating a Counter
                    # yields each distinct KEY once. `sum(1 for v in shipped
                    # if v == obj)` is therefore at most 1 on both sides, so
                    # this compared 1 against 1 however much wider the map
                    # got -- red on a correctly widened artifact, which is the
                    # opposite of what it is for. Counter[obj] is the real
                    # occupied-cell count.
                    self.assertGreater(
                        sum(1 for v in shipped_cells if v == obj),
                        sum(1 for v in expected_cells if v == obj),
                        "the spa map is not actually wider than the donor, so "
                        "the widening did not reach this build",
                    )

    def test_every_lounger_ships_the_same_map(self):
        """They borrow one donor, so a divergence means one missed the fix."""
        for build in self.builds:
            present = [
                build / "Assets" / n
                for n in LOUNGERS
                if (build / "Assets" / n).is_file()
            ]
            if len(present) < 2:
                continue
            with self.subTest(build=build.name):
                digests = {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in present
                }
                # Two groups now, not one: the widened spa pair, and everything
                # else which still ships the donor map untouched. Within each
                # group they must still agree exactly -- a divergence there
                # means one target missed a fix, which is what this test was
                # written to catch.
                widened = {n: d for n, d in digests.items()
                           if n in WIDENED_LOUNGERS}
                plain = {n: d for n, d in digests.items()
                         if n not in WIDENED_LOUNGERS}
                if len(widened) > 1:
                    self.assertEqual(
                        len(set(widened.values())), 1,
                        f"the widened spa loungers disagree: {widened}",
                    )
                if len(plain) > 1:
                    self.assertEqual(
                        len(set(plain.values())), 1,
                        f"the unwidened loungers disagree: {plain}",
                    )
                # And the two groups MUST differ, or the widening never
                # reached this build and every check above passed on
                # unmodified bytes. Only from the release that carries the
                # widening: before it, byte-identical is the CORRECT result.
                if widened and plain and _release_has_widening(build.name):
                    self.assertNotEqual(
                        set(widened.values()), set(plain.values()),
                        "the spa loungers are byte-identical to the plain "
                        "one, so the hotspot widening did not reach this "
                        "build",
                    )


class TestStockDonorBorrowersMatchTheirDonors(unittest.TestCase):
    """The seven stock-donor items must ship their donor's map exactly.

    These are the items that rely on the game's native hotspot path rather
    than this patcher's drop dispatcher. That only works if the placement data
    they carry IS the donor's, so this checks the built artifact rather than
    the manifest that says which donor they name.

    It does NOT establish that a villager dropped on one of these acts. That
    is a separate claim and no playtest has confirmed it.
    """

    BORROWERS = {
        "InvisibleYogaEquipment.png.fmap": "YogaGearStd.png.fmap",
        "HomeGymSystemStd.png.fmap": "YogaGearStd.png.fmap",
        "ExerciseBikeStd.png.fmap": "TreadmillStd.png.fmap",
        "PingPongTableStd.png.fmap": "PoolTableStd.png.fmap",
        "InvisibleHammock.png.fmap": "HammockStd.png.fmap",
        "InvisibleKiddiePool.png.fmap": "PoolChildrensStd.png.fmap",
        "InvisibleFullSizePool.png.fmap": "PoolLargeStd.png.fmap",
    }

    def setUp(self):
        self.builds = list(_finished_builds())
        if not self.builds:
            _refuse_or_skip(self)

    def test_each_borrower_is_byte_identical_to_its_donor(self):
        checked = 0
        for build in self.builds:
            assets = build / "Assets"
            for borrower, donor in self.BORROWERS.items():
                bp, dp = assets / borrower, assets / donor
                if not (bp.is_file() and dp.is_file()):
                    continue
                with self.subTest(build=build.name, fmap=borrower):
                    self.assertEqual(
                        hashlib.sha256(bp.read_bytes()).hexdigest(),
                        hashlib.sha256(dp.read_bytes()).hexdigest(),
                        f"{borrower} no longer matches {donor}; the native "
                        "hotspot path depends on it carrying the donor's map",
                    )
                    checked += 1
        self.assertGreater(
            checked, 0,
            "found no borrower/donor pairs to compare -- a vacuous pass",
        )


if __name__ == "__main__":
    unittest.main()
