#!/usr/bin/env python3
"""Every generated .cpp must actually compile.

This exists because it did not. A merged change added a drawing helper to
vf2_mobile_furniture_behaviors.cpp that used theGraphicsManager, ldwImageGrid,
EImage, CDecal and Decal -- five names that translation unit never declared.
The whole suite passed, because every other test reads the GENERATOR rather
than the C it emits, and the break only surfaced in a real build minutes later.

Each generated unit declares its own types rather than sharing a header, so a
name being declared in four other emitted files buys nothing. That makes "does
this file compile" a question no amount of reading the generator can answer.

Compiling one file takes about a second; a full build takes minutes. The check
is cheap enough that there is no reason for a compile error to ever reach a
build again.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

GENERATED = Path(patcher.PATCHED)

# Where vcvars32.bat lives on a machine that can build this project at all.
# Missing means no toolchain, which is a skip rather than a failure -- the
# generator's own tests still run on a machine that cannot compile.
VCVARS_CANDIDATES = (
    Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat"),
    Path(r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars32.bat"),
)


def _vcvars():
    for path in VCVARS_CANDIDATES:
        if path.is_file():
            return path
    return None


class TestEveryGeneratedUnitCompiles(unittest.TestCase):
    def setUp(self):
        self.vcvars = _vcvars()
        if self.vcvars is None:
            self.skipTest("no Visual Studio toolchain on this machine")
        if not GENERATED.is_dir():
            self.skipTest("no generated sources; run the generator first")
        self.sources = sorted(GENERATED.glob("*.cpp"))
        if not self.sources:
            self.skipTest("no generated .cpp files present")

    def test_each_file_compiles(self):
        """Compile each unit on its own, the way the real build does.

        Copied to a temporary directory so object files never land in the
        repository, and so a failure cannot leave a stale .obj that makes the
        next run look healthy.
        """
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            for source in self.sources:
                shutil.copy2(source, work / source.name)
            for source in self.sources:
                with self.subTest(source.name):
                    result = subprocess.run(
                        f'"{self.vcvars}" >nul 2>&1 && '
                        f'cd /d "{work}" && '
                        f'cl /c /EHsc /nologo "{source.name}"',
                        shell=True, capture_output=True, text=True,
                    )
                    if result.returncode != 0:
                        output = (result.stdout or "") + (result.stderr or "")
                        errors = [
                            line for line in output.splitlines()
                            if "error" in line.lower()
                        ]
                        self.fail(
                            f"{source.name} does not compile:\n  "
                            + "\n  ".join(errors[:10])
                        )

    def test_the_check_is_not_vacuous(self):
        """A deliberately broken file must fail, or this proves nothing.

        Without this, an environment where every compile silently succeeds --
        or where the command never runs -- would report a clean pass.
        """
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            broken = work / "vf2_deliberately_broken.cpp"
            broken.write_text(
                "// Uses a type nothing declares, which is exactly the defect\n"
                "// this module exists to catch.\n"
                "void f() { NoSuchType *p = NoSuchType::Get(); (void)p; }\n",
                encoding="ascii",
            )
            result = subprocess.run(
                f'"{self.vcvars}" >nul 2>&1 && '
                f'cd /d "{work}" && '
                f'cl /c /EHsc /nologo "{broken.name}"',
                shell=True, capture_output=True, text=True,
            )
            self.assertNotEqual(
                result.returncode, 0,
                "a file using an undeclared type compiled successfully, so "
                "this module cannot detect the defect it was written for",
            )


if __name__ == "__main__":
    unittest.main()
