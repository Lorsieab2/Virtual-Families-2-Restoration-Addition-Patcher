#!/usr/bin/env python3
"""The GUI documentation has to keep describing the GUI that ships.

The README and the Transparency Log both describe the wait window and the
settings count. Both are the kind of claim that goes stale silently: a setting
gets added and the count in the prose is still right-looking, or the grab fix
gets reverted and the log still says it was made. Each check here ties a
documented claim to the thing that would falsify it.
"""
import ast
import re
import unittest
from pathlib import Path

import export_offline_patch_bundle as exporter

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
TRANSPARENCY = (ROOT / "docs" / "Transparency Log.txt").read_text(encoding="utf-8")
GUI = (ROOT / "work" / "offline_vf2_patcher_gui.py").read_text(encoding="utf-8")
LEDGER = (ROOT / "docs" / "REQUEST_LEDGER.md").read_text(encoding="utf-8")


class TestTheSettingsCountIsTheRealOne(unittest.TestCase):
    def test_the_readme_states_the_number_of_settings_that_exist(self):
        match = re.search(r"it offers (\d+) settings", README)
        self.assertIsNotNone(match, "the README no longer states a settings count")
        self.assertEqual(
            int(match.group(1)),
            len(exporter.SETTINGS),
            "the README's settings count has drifted from SETTINGS",
        )

    def test_every_setting_is_named_somewhere_in_the_readme(self):
        # A setting a player can tick but cannot look up is undocumented, which
        # is the failure this catches -- not prose quality.
        missing = [s["id"] for s in exporter.SETTINGS if s["label"] not in README]
        self.assertEqual(missing, [], f"settings absent from the README: {missing}")


class TestTheReadmeDoesNotOverclaimRouting(unittest.TestCase):
    """The routed/unrouted split has to survive contact with the prose.

    The first draft of the visible-furniture entry said B180 gave all four
    items a route. Only SpaLoungerStd is routed through this patcher's
    dispatcher; the other three rely on the game's native hotspot path and are
    unconfirmed. Claiming otherwise would promise a player something the build
    cannot support, so the distinction is pinned rather than trusted to prose.
    """

    UNROUTED_VISIBLE = ("Exercise Bike", "Home Gym System", "Ping-Pong Table")

    def test_the_unconfirmed_items_are_named_as_unconfirmed(self):
        entry = next(
            line for line in README.splitlines()
            if line.startswith("- **Four new visible furniture items**")
        )
        for name in self.UNROUTED_VISIBLE:
            with self.subTest(name):
                self.assertIn(name, entry)
        self.assertIn(
            "does not claim they do", entry,
            "the entry must not promise behaviour no player has confirmed",
        )

    def test_the_routed_visible_item_is_still_the_only_one(self):
        # Reads the same source of truth the sibling docs suite uses, so the
        # prose and the route table cannot drift apart independently.
        docs = (ROOT / "work" / "test_b180_docs.py").read_text(encoding="utf-8")
        routed = re.search(r"ROUTED = \{(.*?)\}", docs, re.S).group(1)
        self.assertIn("SpaLoungerStd", routed)
        for absent in ("ExerciseBikeStd", "HomeGymSystemStd", "PingPongTableStd"):
            with self.subTest(absent):
                self.assertNotIn(absent, routed)


class TestTheWaitWindowClaimsHold(unittest.TestCase):
    @staticmethod
    def _code_of(name):
        """A function's statements, with its docstring dropped.

        The docstrings here explain why wait_visibility() is the wrong repair,
        so scanning raw source for that name would match the warning against
        it as readily as a use of it.
        """
        for node in ast.walk(ast.parse(GUI)):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                body = node.body
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    body = body[1:]
                return chr(10).join(
                    ast.get_source_segment(GUI, statement) or "" for statement in body
                )
        return None

    def test_the_log_describes_a_grab_the_code_actually_takes(self):
        self.assertIn('B180 patcher GUI "Please wait" window', TRANSPARENCY)
        code = self._code_of("_take_grab")
        self.assertIsNotNone(code, "the documented bounded grab is gone")
        self.assertIn("raise", code, "an exhausted deadline must surface, not pass")
        self.assertNotIn(
            "wait_visibility",
            code,
            "the log records that wait_visibility is deliberately not used",
        )

    def test_the_documented_centring_behaviour_is_the_implemented_one(self):
        # The log claims only the screen-centred fallback clamps. Pin that, so
        # reintroducing the clamp on the parent-relative branch fails here.
        body = re.search(
            r"def _center\(.*?(?=\n    def )", GUI, re.S
        )
        self.assertIsNotNone(body, "WaitWindow._center is gone")
        parent_branch, _, fallback = body.group(0).partition("screen")
        self.assertNotIn(
            "max(0", parent_branch,
            "the parent-relative branch must not clamp; it throws the window "
            "onto the primary monitor on a multi-monitor desktop",
        )


class TestEveryB180RequestHasALedgerRow(unittest.TestCase):
    """The ledger's own closing rule is that no request is silently omitted.

    A shipped change with no row is exactly the omission that rule exists to
    prevent, and it is invisible: nothing fails, the feature works, and the
    only trace is that a later audit cannot find where it was asked for. Both
    of these were shipped in B180 with no row until this was written.
    """

    def test_the_wait_window_and_the_fmap_work_are_recorded(self):
        for phrase in ('Please wait', 'fmap inheritance'):
            with self.subTest(phrase):
                self.assertIn(phrase, LEDGER, f"no ledger row covers {phrase!r}")

    def test_those_rows_name_the_evidence_not_just_the_outcome(self):
        # A row saying only "shipped" is not usable by a later audit.
        for token in ('0x01B09800', '0x1b0', 'wait_visibility'):
            with self.subTest(token):
                self.assertIn(token, LEDGER)


class TestTheSuiteSkipClaimHolds(unittest.TestCase):
    def test_the_log_records_why_tests_skip_and_they_still_do(self):
        self.assertIn("B180 test suite: inputs a checkout cannot have", TRANSPARENCY)
        for name in (
            "test_mobile_holiday_native_contract.py",
            "test_mobile_sound_route_toggle_contract.py",
        ):
            source = (ROOT / "work" / name).read_text(encoding="utf-8")
            with self.subTest(name):
                self.assertIn(
                    "skipTest", source,
                    "the documented skip is gone; the suite would be red again",
                )


if __name__ == "__main__":
    unittest.main()
