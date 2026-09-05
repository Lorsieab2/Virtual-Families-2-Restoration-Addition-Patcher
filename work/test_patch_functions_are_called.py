#!/usr/bin/env python3
"""Every patch installer must actually be reached.

This exists because two of them were not. `patch_mobile_table_prop_draw` was
written, reviewed, merged and shipped -- and never invoked, so the picnic and
patio sprites installed into every build while nothing drew them. The two prop
ids never enter the engine's prop array, so that wrapper is the only draw there
is; without the call there is no draw at all.

Nothing caught it. The suite reads the generator and confirms the function
exists and is correct. The build runs and reports success, because a function
that is never called cannot fail. The manifest is the only tell, and only if
somebody notices a key that is silently absent rather than wrong.

A defined-but-uncalled installer is invisible to every other kind of check we
have, and it fails in the worst way: quietly, in the shipped build, while the
source looks complete.
"""
import ast
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

SOURCE = Path(patcher.ROOT) / "work" / "patch_mobile_furniture_pack.py"

# Prefixes that mark a function as doing work on the build rather than being a
# helper. These are the ones whose absence from a build is silent.
INSTALLER_PREFIXES = ("patch_", "install_", "sync_", "register_", "write_")

# Functions that are deliberately not called from this module. Each needs a
# reason, so the list cannot quietly become a dumping ground for the very
# defect this test exists to catch.
#
# A caution learned from one of these. "Defined but never called" answers
# whether the FUNCTION is reached; it does not answer whether the FEATURE
# ships. Those come apart exactly when an implementation is replaced and the
# old entry point is left behind -- sync_holiday_body_types looked like a
# dropped feature by every static measure and is in fact superseded by a
# working renderer. Before concluding that an orphan is a lost feature, check
# the build manifest or a real build for whether the thing it was for happens
# by another route.
#
# Checking all three that way was worth it, and the result is worth stating:
# an orphaned installer in a mature codebase is far likelier to be a DECISION
# than an oversight, and the decision is usually recorded somewhere other than
# the code. Two of these three had their rationale sitting in the build
# manifest in plain language, and one of those names a CRASH. Wiring them up
# would have shipped a regression and a crash respectively -- both in the name
# of a fix, and neither visible from reading the generator however carefully.
INTENTIONALLY_UNCALLED = {
    # Found by this module on the day it was written, and recorded rather than
    # fixed: each predates the prop-draw defect and none was named by the owner
    # as broken, so changing them would be work nobody asked for. They are
    # listed so they are visible rather than silently tolerated, and so a NEW
    # orphan still fails the test.
    "patch_multiple_marriage_candidates":
        "an explicitly inert legacy stub -- its own docstring says so, and it "
        "exists to keep old callers resolving",
    "patch_main_scene_outfit_body_apply":
        "DELIBERATELY DISABLED, and wiring it up would CRASH THE GAME. The "
        "build manifest states it outright: outfit_apply_body_resolver is "
        "'disabled for B97 stability', because 'B96 final-apply callsite "
        "replacement made generated Outfit-section items crash on apply'. A "
        "working replacement ships -- the CInventoryManager::GetOutfit hook "
        "reads the selected synthetic ToolTray item directly. The helper "
        "symbol existing and being referenced elsewhere is exactly what makes "
        "this look like forgotten wiring; it is not. Confirmed in the "
        "generator as well as the manifest: outfit_apply_body_resolver is "
        "written TWICE, optimistically inside this orphan and again inside "
        "main(), and main()'s write wins unconditionally. So the "
        "disabled-for-stability record is not stale documentation left lying "
        "around -- it is an active statement made by the shipping build path "
        "on every build, while the orphan's own hopeful status line is the "
        "one that never runs",
    "patch_plan_logging":
        "diagnostic instrumentation, not part of a shipped build",
    "sync_holiday_body_types":
        "SUPERSEDED, not dropped -- checked at the feature level rather than "
        "the function level. The four holiday bodies DO ship, through a "
        "folder-backed runtime renderer, and the build manifest says so "
        "explicitly: holiday_body_types is 'folder-backed runtime renderer "
        "enabled' and records 'spritesheets: not expanded; original sheets "
        "remain fallback'. This function is the old spritesheet-expansion "
        "route that line is declining to use. Wiring it up would re-enable a "
        "superseded implementation alongside the working one -- a regression, "
        "not a restoration",
    "sync_vc90_crt_private_assembly":
        "no VC90 or CRT key appears anywhere in a build manifest, so the "
        "feature does not ship and nothing references it. VC90_CRT_DLL_NAMES "
        "is msvcr90/msvcp90/msvcm90 -- the MSVC 2008 runtimes -- while "
        "desktop_runtime_dlls ships SDL2, SDL2_image, fmod, libjpeg, libpng16 "
        "and zlib1 and no CRT at all. Consistent with being obsolete for this "
        "toolchain. Weaker evidence than the two above, since absence proves "
        "less than a positive statement, but no reason to touch it",
}


def _defined_and_called(tree):
    """Every top-level def, and every name that appears in a Call."""
    defined = {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
        # A function handed off by name rather than called -- a table of
        # installers, a decorator, a getattr -- still counts as reached.
        elif isinstance(node, ast.Name):
            called.add(node.id)
    return defined, called


class TestEveryInstallerIsReached(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        self.defined, self.called = _defined_and_called(self.tree)

    def test_no_installer_is_defined_and_never_used(self):
        """The defect this module exists for.

        `patch_mobile_table_prop_draw` was defined, correct, merged, and
        never invoked. The art shipped; nothing drew it.
        """
        installers = {
            name for name in self.defined
            if name.startswith(INSTALLER_PREFIXES)
        }
        self.assertTrue(installers, "found no installers -- a vacuous pass")

        orphaned = sorted(
            name for name in installers
            if name not in INTENTIONALLY_UNCALLED
            # A definition is itself a Name node in the tree, so require the
            # name to appear more often than its single definition.
            and SOURCE.read_text(encoding="utf-8").count(name) <= 1
        )
        self.assertEqual(
            orphaned, [],
            "these installers are defined but never reached, so the work they "
            "do never happens in a build:\n  " + "\n  ".join(orphaned),
        )

    def test_the_prop_draw_installer_is_called(self):
        """Pinned by name, because this is the one that actually shipped wrong.

        The generic check above would catch it again, but naming it means a
        future reader sees why the module exists at all.
        """
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(
            "def patch_mobile_table_prop_draw(manifest):", source,
            "the prop draw installer is missing entirely",
        )
        self.assertIn(
            "    patch_mobile_table_prop_draw(manifest)", source,
            "the prop draw installer is defined but never called, so the "
            "picnic meal and patio drinks ship as art that nothing draws",
        )

    def test_every_exception_carries_a_reason(self):
        """The allow-list must not become a place to hide this defect."""
        for name, reason in INTENTIONALLY_UNCALLED.items():
            with self.subTest(name):
                self.assertTrue(
                    reason and reason.strip(),
                    f"{name} is excused from this check with no reason given",
                )


if __name__ == "__main__":
    unittest.main()
