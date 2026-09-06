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
    "patch_vf3_style_child_adoption_chooser":
        "REVERTED BECAUSE IT CRASHED THE GAME, and found only once this "
        "module stopped deciding reachability by counting the name in the "
        "file text -- it is referenced twice in comments, one of them a "
        "commented-out call, which the old text count accepted as reached. "
        "It replaced the stock spawn route in "
        "CScrollingStoreScene::HandleUpgrade (+0x57A) with a helper that "
        "put up a baby-or-older-child message box and spawned the adoptee "
        "itself. Purchasing Adoption Services then access-violated with a "
        "faulting module of 'unknown' at address 0x1D7 -- execution had "
        "left every loaded module, which is the signature of a call "
        "through a corrupted return address or function pointer, not a bad "
        "data read. The helper also did not reproduce the stock call: the "
        "native route is SpawnSpecificPeep(age=1, gender=-1, body=0x3C) "
        "and it passed body=-1 with an explicit gender, and it built a "
        "theMessageBoxDlg in a 0x300-byte stack buffer standing in for a "
        "class whose real size is not pinned anywhere. Rather than guess "
        "which of those was fatal, the whole route was reverted so "
        "HandleUpgrade's adoption path is byte-identical to stock, and "
        "Adoption Services is deliberately left ENTIRELY BASE-GAME",
    "write_vc90_crt_manifest":
        "reachable ONLY from sync_vc90_crt_private_assembly, which is "
        "itself allow-listed below. It is here because the check now "
        "walks the call graph from module scope rather than collecting "
        "every name that appears in a Call: under the old flat rule an "
        "installer called solely from another orphan inherited that "
        "orphan's exemption silently, and this function was the live "
        "example. It carries no reason of its own beyond its caller's -- "
        "if sync_vc90_crt_private_assembly is ever wired up, this entry "
        "should go with it",
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


def _own_scope_nodes(node):
    """Every node in this scope, NOT descending into nested scopes.

    ast.walk descends into nested function, lambda and class bodies. Defining
    a class whose method mentions patch_new() does not execute that method, and
    defining an inner helper that a reachable function never calls does not
    execute it either -- so walking eagerly through them reports an orphan as
    reached. Each nested scope is a separate graph node, reached only when
    something actually references it.
    """
    nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
    # The node ITSELF counts: a decorator or a default argument is handed to
    # this helper as a bare Name, and yielding only its children would miss it.
    # A nested scope passed in directly is still descended into, because the
    # caller asked about that scope specifically.
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        # Stop at a nested scope -- unless it is the node the caller asked
        # about, whose own body is exactly what they want walked.
        if current is not node and isinstance(current, nested):
            continue
        for child in ast.iter_child_nodes(current):
            stack.append(child)


def _bound_locally(node):
    """Names this scope BINDS, which therefore shadow a module-level function.

    A parameter, an assignment target, a walrus, a for-loop variable, an
    `except ... as`, a `with ... as`, an import alias, or a nested def/class
    all create a local binding. `patch_new = lambda: None; patch_new()` inside
    a reachable function refers to that local, not to the top-level installer
    of the same name, so counting it would mark an orphan reached by a
    statement that never touches it.

    Only the scope's OWN bindings are collected; nested scopes are separate.
    """
    bound = set()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = node.args
        every = (
            list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
            + ([args.vararg] if args.vararg else [])
            + ([args.kwarg] if args.kwarg else [])
        )
        for arg in every:
            bound.add(arg.arg)
    for child in _own_scope_nodes(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            bound.add(child.id)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(child.name)
        elif isinstance(child, (ast.Import, ast.ImportFrom)):
            for alias in child.names:
                bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(child, ast.ExceptHandler) and child.name:
            bound.add(child.name)
    return bound


def _references_within(node):
    """Names this node genuinely REFERENCES, excluding four false positives.

    * An assignment TARGET. `patch_new = None` contains an ast.Name for
      patch_new but binds it rather than using it -- counting it would mark an
      installer reached by the very statement that shadows it.
    * An attribute call on another object. `obj.patch_new()` yields the
      attribute "patch_new", which has nothing to do with the top-level
      function of that name.
    * A LOCALLY BOUND name. A parameter or local variable that happens to share
      an installer's name refers to the local, so it is dropped here.
    * Anything inside a NESTED scope. Defining a class or an inner function
      does not run its body; those scopes are separate graph nodes, walked only
      once something actually references them.

    A bare LOAD still counts: a function placed in a table, passed to a helper,
    or wrapped by a decorator is genuinely reachable, and the generator does
    that in several places.
    """
    shadowed = _bound_locally(node)
    names = set()
    for child in _own_scope_nodes(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id not in shadowed:
                names.add(child.func.id)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            if child.id not in shadowed:
                names.add(child.id)
    return names


def _reachable_from_module(tree):
    """Every top-level def, and those REACHABLE from module scope.

    Reachability is a call-graph walk from the module body, not a flat set of
    every name that appears in a Call anywhere. A flat set counts calls made
    from INSIDE an orphan, so an installer invoked only by another orphan reads
    as reached.

    That is not hypothetical: write_vc90_crt_manifest is called only by
    sync_vc90_crt_private_assembly, which is itself deliberately allow-listed
    as uncalled. Under the flat rule the inner writer passed without an
    allow-list entry of its own, so any new installer called solely from
    another orphan would have gone undetected.

    The allow-list is applied as a FRONTIER, not as an exemption: an
    intentionally-uncalled function does not seed the walk, so what only it
    calls stays unreachable too.
    """
    defined = {
        node.name: node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    # Seed: everything referenced from module scope -- statements that actually
    # execute on import, plus decorators and default arguments, which run then
    # too. Function BODIES are deliberately excluded here; they are only walked
    # once their own function is known to be reachable.
    seed = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                seed |= _references_within(deco)
            for default in node.args.defaults + [d for d in node.args.kw_defaults if d]:
                seed |= _references_within(default)
        else:
            seed |= _references_within(node)

    reachable, frontier = set(), [n for n in seed if n in defined]
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        # An intentionally-uncalled function does not extend the walk. If it
        # did, everything it calls would inherit its exemption.
        if name in INTENTIONALLY_UNCALLED:
            continue
        for referenced in _references_within(defined[name]):
            if referenced in defined and referenced not in reachable:
                frontier.append(referenced)
    return set(defined), reachable


class TestEveryInstallerIsReached(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        self.defined, self.called = _reachable_from_module(self.tree)

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

        # Reachability is decided from the AST call set, NOT from counting
        # the name in the file text. A text count is satisfied by a mention
        # in a comment or a docstring, which is exactly how an orphan hides:
        # patch_vf3_style_child_adoption_chooser is defined once, referenced
        # only from two comments (one of them a commented-out call), and the
        # old text-count rule passed it as reached.
        orphaned = sorted(
            name for name in installers
            if name not in INTENTIONALLY_UNCALLED
            and name not in self.called
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


class AllowListedInstallersStayUncalled(unittest.TestCase):
    """Re-enabling one of these must FAIL, not pass quietly.

    The allow-list is applied as a frontier during the call-graph walk: an
    intentionally-uncalled function is added to `reachable` and then does not
    extend the walk. That is right for detecting orphans hidden behind orphans,
    and it has a hole at the other end -- if somebody CALLS one of these from
    main(), the walk marks it reachable, the orphan assertion excludes it by
    name anyway, and the suite stays green.

    Two of the seven would do real damage that way:

      patch_vf3_style_child_adoption_chooser -- reverted because it CRASHED
        the game; purchasing Adoption Services access-violated with a faulting
        module of "unknown" at 0x1D7.
      patch_main_scene_outfit_body_apply -- disabled for stability; the build
        manifest records that the B96 final-apply callsite replacement made
        generated Outfit-section items crash on apply.

    Uncommenting either would ship a known crash with every check green, and
    the allow-list entry explaining why it is uncalled would become a lie.
    """

    def setUp(self):
        self.tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        self.defined, self.reachable = _reachable_from_module(self.tree)

    def test_no_allow_listed_installer_is_reachable(self):
        wrongly_reachable = sorted(
            name for name in INTENTIONALLY_UNCALLED
            if name in self.reachable
        )
        self.assertEqual(
            wrongly_reachable, [],
            "these functions are recorded as intentionally uncalled but are "
            "now REACHED from module scope:\n  "
            + "\n  ".join(wrongly_reachable)
            + "\nEither the call is a mistake -- two of these are recorded as "
            "crashing the game -- or the function genuinely ships now and its "
            "allow-list entry is stale. Both need a decision, not a green "
            "suite.",
        )

    def test_every_allow_listed_name_is_actually_defined(self):
        """A stale entry hides the next orphan that takes its name."""
        missing = sorted(
            name for name in INTENTIONALLY_UNCALLED
            if name not in self.defined
        )
        self.assertEqual(
            missing, [],
            "these allow-list entries name functions that no longer exist, so "
            "the entry is dead weight and would silently exempt a future "
            "function of the same name:\n  " + "\n  ".join(missing),
        )


class TheReachabilityWalkResolvesScopes(unittest.TestCase):
    """The walk must answer both questions, not just the safe one.

    A reachability check has two ways to be wrong and only one of them is
    loud. Reporting a called installer as an orphan fails the suite and gets
    fixed. Reporting an ORPHAN as reached is silent -- it is the defect this
    module exists to catch, and it is what every case below reproduced before
    the traversal resolved scopes and lexical bindings.

    So each case is asserted in BOTH directions: the shapes that must not
    count as reachable, and the shapes that genuinely are and must survive.
    A stricter walk that quietly stopped seeing real handoffs would pass a
    one-sided version of this test while breaking the generator's own wiring.
    """

    UNREACHABLE = {
        "a class method that mentions it": (
            "def patch_new(): pass\n"
            "class Unused:\n"
            "    def go(self): patch_new()\n"
        ),
        "a local that shadows it, then is called": (
            "def patch_new(): pass\n"
            "def entry():\n"
            "    patch_new = lambda: None\n"
            "    patch_new()\n"
            "entry()\n"
        ),
        "a parameter that shadows it": (
            "def patch_new(): pass\n"
            "def entry(patch_new): patch_new()\n"
            "entry(None)\n"
        ),
        "a nested def that is never called": (
            "def patch_new(): pass\n"
            "def entry():\n"
            "    def inner(): patch_new()\n"
            "entry()\n"
        ),
        "an assignment target": "def patch_new(): pass\npatch_new = None\n",
        "an attribute on another object": "def patch_new(): pass\nobj.patch_new()\n",
    }

    REACHABLE = {
        "a direct call from module scope": "def patch_new(): pass\npatch_new()\n",
        "a call from a reachable function": (
            "def patch_new(): pass\ndef entry(): patch_new()\nentry()\n"
        ),
        "a call two levels down": (
            "def patch_new(): pass\n"
            "def middle(): patch_new()\n"
            "def top(): middle()\n"
            "top()\n"
        ),
        "a handoff into a table": "def patch_new(): pass\nTABLE = [patch_new]\n",
        "use as a decorator": "def patch_new(): pass\n@patch_new\ndef x(): pass\n",
        "use as a default argument": (
            "def patch_new(): pass\ndef entry(f=patch_new): pass\n"
        ),
    }

    def test_these_shapes_do_not_make_an_orphan_look_reached(self):
        for description, source in self.UNREACHABLE.items():
            with self.subTest(description):
                _, reachable = _reachable_from_module(ast.parse(source))
                self.assertNotIn(
                    "patch_new",
                    reachable,
                    f"{description} reported an uncalled installer as reached, "
                    "which is the silent orphan this module exists to catch",
                )

    def test_genuine_reachability_still_counts(self):
        for description, source in self.REACHABLE.items():
            with self.subTest(description):
                _, reachable = _reachable_from_module(ast.parse(source))
                self.assertIn(
                    "patch_new",
                    reachable,
                    f"{description} is real wiring the generator uses, and a "
                    "walk that misses it would report false orphans",
                )


if __name__ == "__main__":
    unittest.main()
