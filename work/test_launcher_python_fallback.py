#!/usr/bin/env python3
"""The generated launchers must actually reach their `python` fallback.

`cmd` substitutes `%ERRORLEVEL%` when it *parses* a parenthesised block, not
when the block runs. A test written that way inside

    if not defined VF2_PY (
      where python >nul 2>nul
      if %ERRORLEVEL%==0 set "VF2_PY=python"
    )

therefore reads the errorlevel from before the block started, so the fallback
never fires and anyone without a registered `py -3` is told to install the
Python they already have. `if not errorlevel 1` is evaluated as the line runs
and is the correct form.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "work" / "export_offline_patch_bundle.py"

PROBE_START = "where py >nul 2>nul"
PROBE_END = 'if not defined VF2_PY ('


def _probe_blocks():
    """Each launcher's Python-discovery block, from `where py` to the guard
    that follows the fallback."""
    source = EXPORTER.read_text(encoding="utf-8")
    blocks = []
    cursor = 0
    while True:
        start = source.find(PROBE_START, cursor)
        if start < 0:
            break
        # the block of interest ends at the "could not find Python" guard,
        # which is the second `if not defined VF2_PY (` after the probe
        first = source.find(PROBE_END, start)
        second = source.find(PROBE_END, first + 1) if first >= 0 else -1
        end = second if second >= 0 else len(source)
        blocks.append(source[start:end])
        cursor = end
    return blocks


class TestLauncherPythonFallback(unittest.TestCase):
    def test_both_launchers_are_covered(self):
        self.assertEqual(
            len(_probe_blocks()), 2,
            "expected the apply launcher and the GUI launcher to both probe for Python",
        )

    def test_probes_use_the_dynamic_errorlevel_test(self):
        for block in _probe_blocks():
            self.assertNotIn(
                "%ERRORLEVEL%", block,
                "use `if not errorlevel 1`: %ERRORLEVEL% is expanded when the "
                "block is parsed, so it cannot see the command inside it",
            )

    def test_the_python_fallback_is_actually_present(self):
        for block in _probe_blocks():
            self.assertIn('set "VF2_PY=python"', block)
            self.assertIn("where python >nul 2>nul", block)


if __name__ == "__main__":
    unittest.main()
