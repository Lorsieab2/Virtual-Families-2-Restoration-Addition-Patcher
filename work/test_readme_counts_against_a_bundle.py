#!/usr/bin/env python3
"""README counts describe what a bundle carries, so a bundle must confirm them.

Two defects reached B180 because README numbers were checked against source
constants instead of a manifest. Both looked correct in review, because the
prose and the assertion were derived from the same wrong authority:

  * "it offers 36 settings" was len(SETTINGS); the bundle carries 35, since
    two settings are deliberately withheld and one is added during export.
  * "20 verified mobile renovation images" counted Bathroom 1 and Bathroom 2
    together; Bathroom 2's art is gated on a different setting and ships
    under its own entry, so Add mobile room renovations carries 15.

The exporter is not a valid check on a claim about a bundle. This suite reads
a built manifest and, when a release archive is available, the archive itself.
It is skipped rather than failed where neither exists -- a machine with no
build output cannot answer the question, and pretending otherwise is how the
suite went red for everyone once already.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
import zipfile
from pathlib import Path

# Run either as `python -m unittest test_...` from work/ or as
# `python -m unittest work.test_...` from the repo root; the latter puts the
# repo root on sys.path rather than work/, so the sibling import needs help.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import export_offline_patch_bundle as exporter

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _current_release() -> str | None:
    """The release these docs describe, read from the repo rather than typed.

    An older archive left in outputs/ is not evidence about the current build.
    The first version of this helper sorted archives by name and happily
    validated the README against B178 while B180 was the release -- reporting
    a failure that was two releases stale, which is the same wrong-authority
    mistake these tests exist to catch.
    """
    def label(path):
        return re.search(r"B(\d+(?:\.\d+)*)", path.name).group(1)

    def order(path):
        # B180.1 sorts after B180, and B99 before B100.
        return tuple(int(part) for part in label(path).split("."))

    identities = sorted(
        (ROOT / "data" / "vf2").glob("release-identities-B*.json"), key=order
    )
    if identities:
        return "B" + label(identities[-1])
    return None


def _manifest():
    """The current release's manifest, or None.

    A release archive is preferred -- it is what a player actually receives --
    but ONLY when it is the current release. A build-output manifest is the
    fallback, and a stale archive is ignored rather than quietly answered
    from.
    """
    current = _current_release()
    def archive_label(path):
        found = re.search(r"(B\d+(?:\.\d+)*)-Release", path.name)
        return found.group(1) if found else ""

    for archive in sorted(
        ROOT.rglob("VF2-B*-Release.zip"),
        key=lambda p: tuple(
            int(x) for x in (archive_label(p) or "B0")[1:].split(".")
        ),
        reverse=True,
    ):
        # Compare the COMPLETE label: "B180" is a prefix of "B180.1", so a
        # substring test would accept the stale base release as current.
        if current and archive_label(archive) != current:
            continue
        try:
            with zipfile.ZipFile(archive) as bundle:
                names = [n for n in bundle.namelist() if n.endswith("manifest.json")]
                if names:
                    return json.loads(bundle.read(names[0])), f"archive {archive.name}"
        except (zipfile.BadZipFile, OSError):
            continue
    for path in sorted(
        (ROOT / "outputs").rglob("manifest.json"), key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        # A build folder from an older release is no better evidence than an
        # older archive. Anything naming a different release is skipped;
        # anything naming no release at all is a working build of the current
        # tree and is accepted.
        stamped = re.search(r"B\d+(?:\.\d+)*", path.parent.name)
        if stamped and current and stamped.group(0) != current:
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8")), f"build {path.parent.name}"
        except (OSError, json.JSONDecodeError):
            continue
    return None, None


class ReadmeCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.source = _manifest()
        if cls.manifest is None:
            raise unittest.SkipTest(
                "needs a built manifest or a release archive; neither is present"
            )

    def _records(self):
        return self.manifest.get("asset_patches", []) + self.manifest.get(
            "post_asset_patches", []
        )

    def _pngs_requiring(self, setting):
        found = set()
        for record in self._records():
            requires = record.get("requires")
            requires = requires if isinstance(requires, list) else (
                [requires] if requires else []
            )
            path = record.get("file_path", "")
            if setting in requires and path.endswith(".png"):
                found.add(path)
        return found

    def test_the_offered_settings_count_matches_the_manifest(self):
        self.assertIn(
            f"bundle offers {len(self.manifest['settings'])} settings",
            README,
            f"README disagrees with {self.source}, which carries "
            f"{len(self.manifest['settings'])} settings",
        )

    def test_the_renovation_count_excludes_the_bathroom_2_art(self):
        """Room images only -- store icons and curtains are not renovations."""
        rooms = {
            p for p in self._pngs_requiring("mobile_renovations")
            if "/store_icons/" not in p and "/curtains/" not in p
        }
        self.assertIn(
            f"{len(rooms)} verified mobile renovation images",
            README,
            f"README disagrees with {self.source}, which carries {len(rooms)} "
            "room images under mobile_renovations",
        )

    def test_bathroom_2_art_is_gated_on_its_own_setting(self):
        """The reason the two counts are separate, pinned so it stays true."""
        own = self._pngs_requiring("ai_generated_bathroom2_renovations")
        self.assertTrue(own, "Bathroom 2 art is no longer gated on its own setting")
        shared = own & self._pngs_requiring("mobile_renovations")
        self.assertEqual(
            shared, set(), "Bathroom 2 art must not also ship under mobile_renovations"
        )

    def test_the_behavior_map_count_matches_the_manifest(self):
        maps = {
            r.get("file_path", "") for r in self._records()
            if r.get("file_path", "").endswith(".fmap")
            and "mobile_furniture_behaviors" in (
                r.get("requires") if isinstance(r.get("requires"), list)
                else [r.get("requires")]
            )
        }
        self.assertIn(f"Ships {len(maps)} behavior maps", README)

    def test_the_renovation_setting_description_matches_what_it_installs(self):
        """The GUI description is a promise made at the checkbox.

        It said 20 images, counting Bathroom 1 and Bathroom 2 together, while
        the setting installs 15 -- Bathroom 2's art is gated on a different
        setting a player can decline independently. That text is not merely
        documentation: it is shown next to the checkbox in the patcher and
        copied into the Transparency Log the bundle ships, so B180 reached
        every player overstating the setting by five images.

        The assertion is against the EXPORTER, not the manifest, and that
        distinction is the point. A published bundle cannot be edited, so
        checking the shipped manifest would fail forever on B180 and force
        someone to weaken the test to get a green board. Checking the source
        of the text proves the next bundle is right while leaving the shipped
        defect recorded rather than papered over.
        """
        rooms = {
            p for p in self._pngs_requiring("mobile_renovations")
            if "/store_icons/" not in p and "/curtains/" not in p
        }
        description = next(
            s["description"] for s in exporter.SETTINGS
            if s["id"] == "mobile_renovations"
        )
        self.assertIn(
            f"{len(rooms)} verified mobile renovation images",
            description,
            f"the setting's description disagrees with the {len(rooms)} images "
            f"it installs, per {self.source}",
        )

    def test_the_shipped_bundle_is_allowed_to_carry_the_old_wording(self):
        """B180's manifest is wrong and cannot be changed. Say so here.

        Without this, the failure above would be the only trace, and the
        obvious way to make it pass is to delete it. Recording the known
        divergence keeps the fact visible and keeps the board honest.
        """
        shipped = next(
            (s["description"] for s in self.manifest["settings"]
             if s["id"] == "mobile_renovations"), ""
        )
        source = next(
            s["description"] for s in exporter.SETTINGS
            if s["id"] == "mobile_renovations"
        )
        if not shipped or shipped == source:
            return
        # The exception is B180's alone. Left unconditional it would excuse the
        # SAME stale wording in any future bundle -- the exact divergence this
        # is meant to detect -- because shipped != source would still hold.
        self.assertEqual(
            _current_release(), "B180",
            f"{self.source} diverges from source; only B180 is known to, and "
            "a later bundle must match the exporter rather than inherit its "
            "exception",
        )
        self.assertIn(
            "20 verified", shipped,
            "B180's divergence is its renovation count and nothing else",
        )

    def test_the_ornament_count_in_its_description_is_right(self):
        """Checked because it is the same shape, and it is correct.

        Recorded so a later pass does not 'fix' a claim that already matches:
        twelve collectible images ship, and the description says twelve.
        """
        ornaments = {
            p for p in self._pngs_requiring("holiday_ornaments_collection")
            if "CollectionOrnaments/" in p
        }
        description = next(
            s["description"] for s in self.manifest["settings"]
            if s["id"] == "holiday_ornaments_collection"
        )
        self.assertIn(f"{len(ornaments)} yard collectibles", description)



if __name__ == "__main__":
    unittest.main()


class DisclosureOfShippedDefectsTests(unittest.TestCase):
    """The disclosure guard must not depend on having a bundle.

    It first lived inside the bundle-backed class, so on a clean checkout --
    where outputs/ and *.zip are gitignored -- the whole class skipped and
    deleting the disclosure passed the suite. A guard that only runs on the
    one machine holding a release archive is not a guard; it is the same
    vacuous pass this file was written to eliminate, reintroduced by putting
    a check behind a precondition it does not need.

    Nothing here reads a build artifact. B180 is published and immutable, so
    the fact it shipped an overstated renovation count is a fixed historical
    fact, checkable from the repository alone.
    """

    LOG = ROOT / "docs" / "Transparency Log.txt"
    ENTRY = "B180 shipped an overstated count in one setting description"

    def test_the_b180_overstatement_stays_disclosed(self):
        log = self.LOG.read_text(encoding="utf-8")
        self.assertIn(
            self.ENTRY, log,
            "B180 shipped a player-visible overstatement; the Transparency Log "
            "must say so, whether or not a bundle is available to check",
        )

    def test_the_disclosure_says_what_was_wrong_and_what_was_not(self):
        """A disclosure that only admits fault is not usable.

        A reader needs the real number, and needs to know their install is not
        affected -- otherwise the honest thing reads as a bigger problem than
        it is.
        """
        log = self.LOG.read_text(encoding="utf-8")
        # Fail with the reason rather than an IndexError from the split below:
        # a missing entry is the sibling test's business, not a crash here.
        self.assertIn(self.ENTRY, log, "the disclosure entry is gone")
        entry = log.split(self.ENTRY)[1].split(chr(10) + "B180 ")[0]
        for token in ("15", "20", "Bathroom 2"):
            with self.subTest(token):
                self.assertIn(token, entry)
        self.assertIn(
            "no asset", entry.lower(),
            "the entry must state that nothing a player receives behaves "
            "differently, or it overstates the defect in the other direction",
        )

    def test_the_source_now_carries_the_corrected_count(self):
        # The disclosure claims it is fixed at source. Check that, so the log
        # cannot describe a repair that was never made.
        description = next(
            row["description"] for row in exporter.SETTINGS
            if row["id"] == "mobile_renovations"
        )
        self.assertIn("15 verified mobile renovation images", description)
        self.assertNotIn("20 verified", description)

