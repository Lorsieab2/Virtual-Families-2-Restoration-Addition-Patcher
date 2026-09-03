#!/usr/bin/env python3
"""The 0% pregnancy guard ships with the embrace hook, not with Behavior Patches.

`patch_villager_same_sex_embrace` is installed in every build. The guard that
holds a same-sex marriage to its promised 0% pregnancy rate used to live inside
`patch_six_child_private_time`, which `main()` runs only when Behavior Patches
is enabled. In the behaviour-disabled executable an enabled same-sex couple
could therefore reach behaviour 358 and an unguarded `TryToMakeBaby`, where the
native gender-blind `ChanceOfPregnancy`/`Impregnate` path could start a
pregnancy.

The two are separate patches now, and this pins them that way.
"""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "work" / "patch_mobile_furniture_pack.py"

GUARD = "patch_same_sex_pregnancy_guard"
EMBRACE = "patch_villager_same_sex_embrace"
SIX_CHILD = "patch_six_child_private_time"


def _main_body():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("main() not found")


def _calls_at_top_level(body):
    """Names called directly in this block, not inside any nested `if`."""
    names = set()
    for stmt in body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            fn = stmt.value.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
    return names


def _calls_under_gate(node, gate):
    names = set()
    for stmt in ast.walk(node):
        if not isinstance(stmt, ast.If):
            continue
        test = stmt.test
        if isinstance(test, ast.Name) and test.id == gate:
            names |= _calls_at_top_level(stmt.body)
    return names


class TestGuardIsUnconditional(unittest.TestCase):
    def setUp(self):
        self.main = _main_body()

    def test_the_guard_is_its_own_patch(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(f"def {GUARD}(", source)

    def test_the_guard_runs_ungated(self):
        self.assertIn(GUARD, _calls_at_top_level(self.main.body),
                      "the guard must not sit behind any gate in main()")

    def test_the_guard_is_not_behind_behavior_patches(self):
        gated = _calls_under_gate(self.main, "ENABLE_BEHAVIOR_PATCHES")
        self.assertNotIn(GUARD, gated)

    def test_it_ships_wherever_the_embrace_hook_does(self):
        top = _calls_at_top_level(self.main.body)
        self.assertIn(EMBRACE, top)
        self.assertIn(GUARD, top)

    def test_the_six_child_bypass_stays_optional(self):
        # That half really is a behaviour change and belongs behind the gate.
        self.assertIn(SIX_CHILD, _calls_under_gate(self.main, "ENABLE_BEHAVIOR_PATCHES"))
        self.assertNotIn(SIX_CHILD, _calls_at_top_level(self.main.body))

    def test_the_guard_no_longer_lives_inside_the_six_child_patch(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == SIX_CHILD:
                body = ast.get_source_segment(
                    SOURCE.read_text(encoding="utf-8"), node
                )
                # The install, not the word: the manifest still points at
                # the separate guard by name.
                self.assertNotIn("SAME_SEX_TRY_TO_MAKE_BABY_SKIP_HELPER_SYMBOL", body)
                self.assertNotIn("try_trampoline", body)
                return
        raise AssertionError(f"{SIX_CHILD} not found")


if __name__ == "__main__":
    unittest.main()
