#!/usr/bin/env python3
"""The prop sprites must be WRITTEN by the build, not merely tracked.

test_prop_art_is_tracked.py checks the files exist in the repository with the
right dimensions and digests. That is necessary and not sufficient: the
exporter builds a bundle by diffing the build output against a clean base, so
a sprite the generator never writes is a sprite a player never receives.

The failure that would cause is the quiet kind. A wrapper drawing these props
would work on the machine that has the repository checked out and show nothing
on a real install, with the art visibly present in the source tree the whole
time.

The precedent is install_new_furniture_art, whose sprites do reach players --
SpaLoungerStd.png ships at payload/Images/Furniture/SpaLoungerStd.png in the
B180 archive -- and it gets there by being written into the build output, not
by being named in the exporter.
"""
import hashlib
import json
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

ROOT = Path(__file__).resolve().parents[1]
ART = (
    ROOT / "patcher_assets" / "optional_patches" / "mobile_furniture_behaviors"
    / "prop_art"
)


class TestThePropArtIsEmittedByTheBuild(unittest.TestCase):
    def test_the_installer_exists_and_is_called(self):
        """Defining it without calling it is the same as not having it.

        This reads the GENERATOR, which is a weaker claim than it looks: it
        says the code to copy the art exists, not that the art reached a
        build. The artifact-level check is the sibling below, and it is the
        one that actually answers the question.
        """
        source = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def install_prop_art(manifest):", source)
        self.assertIn("    install_prop_art(manifest)", source)

    def test_the_sprites_are_in_a_build_that_ran_the_installer(self):
        """Ask a build output, not the generator that would produce one.

        Reading the generator and concluding the art ships is the same
        mistake that let the art be tracked-but-unshipped in the first place:
        a claim about what a player receives, checked against a file in the
        repository.

        Only builds newer than the installer can pass, so this skips on older
        ones rather than failing them -- B180 predates install_prop_art and
        legitimately does not contain these sprites.
        """
        builds = sorted(
            d for d in (ROOT / "outputs").glob("VF2-*-matrix-*")
            if (d / "Images").is_dir() and list(d.glob("*.exe"))
        )
        if not builds:
            self.skipTest("no finished build output in this tree")
        fresh = [
            d for d in builds
            if all((d / "Images" / n).is_file() for n in patcher.PROP_ART_INSTALL)
        ]
        if not fresh:
            self.skipTest(
                "no build newer than install_prop_art; the newest predates it "
                "and correctly lacks these sprites"
            )
        for build in fresh:
            for source_name, target_name in patcher.PROP_ART_INSTALL.items():
                with self.subTest(build=build.name, sprite=target_name):
                    shipped = (build / "Images" / target_name).read_bytes()
                    tracked = (ART / source_name).read_bytes()
                    self.assertEqual(
                        hashlib.sha256(shipped).hexdigest(),
                        hashlib.sha256(tracked).hexdigest(),
                        "the built sprite differs from the tracked source",
                    )

    def test_every_tracked_sprite_is_installed(self):
        """No sprite may be tracked but left out of the install map.

        A file added to prop_art/ and forgotten here would sit in the
        repository looking shipped while never reaching a build.
        """
        tracked = {p.name for p in ART.glob("*.png")}
        installed = set(patcher.PROP_ART_INSTALL)
        self.assertEqual(
            tracked, installed,
            "prop_art/ and PROP_ART_INSTALL disagree; every tracked sprite "
            "must be installed and every installed name must be tracked",
        )
        self.assertTrue(tracked, "found no prop art to check -- a vacuous pass")

    def test_the_digest_manifest_covers_every_sprite(self):
        """The installer refuses to write art whose digest it cannot check."""
        sums = ART / "SHA256SUMS.json"
        self.assertTrue(sums.is_file(), f"{sums.name} is missing")
        digests = json.loads(sums.read_text(encoding="utf-8"))["files"]
        for name in sorted(patcher.PROP_ART_INSTALL):
            with self.subTest(sprite=name):
                self.assertIn(name, digests, "no recorded digest")
                actual = hashlib.sha256((ART / name).read_bytes()).hexdigest()
                self.assertEqual(
                    digests[name], actual,
                    f"{name} does not match its recorded digest; hand-supplied "
                    "art cannot be regenerated, so this must fail the build",
                )

    def test_the_digest_count_matches(self):
        sums = json.loads((ART / "SHA256SUMS.json").read_text(encoding="utf-8"))
        self.assertEqual(sums["count"], len(sums["files"]))


if __name__ == "__main__":
    unittest.main()
