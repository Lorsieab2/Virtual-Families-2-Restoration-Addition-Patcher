"""scripts/run_tests_parallel.py and scripts/release_only.py keep their lists honest.

The runner covers tests/ and work/. Its SERIAL list names files that write fixed paths other files read, and
WHOLE names files that must never be split over two processes; release_only.RELEASE_ONLY names the slow tests
an ordinary run skips. A name in any of them that matches nothing would silently stop doing its job, so every
entry must name a real file or test.
"""
import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load("run_tests_parallel")
release_only = _load("release_only")


def _defined_tests(path: Path) -> set:
    """"Class::test" and "test" names defined in a test file, read without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(f"{node.name}::{child.name}")
    return names


def test_every_serial_and_whole_entry_is_a_real_test_file():
    for listed in (runner.SERIAL, runner.WHOLE):
        assert len(listed) == len(set(listed))
        for name in listed:
            path = ROOT / name
            assert path.is_file(), f"{name} does not exist"
            assert path.parent.name in runner.SUITES and path.name.startswith("test_")
    assert not set(runner.SERIAL) & set(runner.WHOLE)


def test_a_file_that_rebuilds_a_companion_dll_is_never_split():
    # runtime/build/vf2time_b200*.dll and vf2kids_b200*.dll are fixed paths; two processes of one file that
    # runs the build batch file would build the same DLL at the same moment.
    builders = [runner.rel(p) for p in runner.suite_files("all")
                if p.resolve() != Path(__file__).resolve() and any(bat in p.read_text(encoding="utf-8", errors="replace")
                       for bat in ("build_b200time.bat", "build_b200kids.bat", "build_b200history.bat",
                                   "build_b200outfits.bat", "build_b200refresh.bat"))]
    assert builders, "no test runs the companion DLL builds any more; review WHOLE"
    for name in builders:
        assert name in runner.WHOLE or name in runner.SERIAL, f"{name} rebuilds runtime/build; add it to WHOLE"


def test_every_release_only_entry_names_a_real_test():
    assert len(release_only.RELEASE_ONLY) == len(set(release_only.RELEASE_ONLY))
    for entry in release_only.RELEASE_ONLY:
        file, test = entry.split("::", 1)
        path = ROOT / file
        assert path.is_file(), f"RELEASE_ONLY names {file}, which does not exist"
        assert test.split("[", 1)[0] in _defined_tests(path), f"RELEASE_ONLY names {entry}, which is not defined"


def test_the_runner_covers_both_suites_and_only_test_files():
    files = runner.suite_files("all")
    assert {p.parent.name for p in files} == {"tests", "work"}
    assert files == sorted((ROOT / "tests").glob("test_*.py")) + sorted((ROOT / "work").glob("test_*.py"))


def test_the_tests_suite_is_what_ci_collects():
    # CI runs `python -m pytest tests/ --release`, which collects tests/test_*.py (pytest's default
    # python_files also matches *_test.py; there are none, and this keeps it that way).
    assert not list((ROOT / "tests").glob("*_test.py"))
    assert runner.suite_files("tests") == sorted((ROOT / "tests").glob("test_*.py"))


def test_a_release_run_runs_every_test_exactly_once():
    files = runner.suite_files("all")
    for release in (False, True):
        parallel, serial = runner.units(files, release)
        whole_files = [u["file"] for u in parallel + serial if u["node"] is None]
        assert sorted(whole_files) == sorted(runner.rel(f) for f in files)
        nodes = [f"{u['file']}::{u['node']}" for u in parallel if u["node"]]
        assert len(nodes) == len(set(nodes))
        if not release:
            assert not nodes and not any(u["deselect"] for u in parallel)
            continue
        split = {u["file"] for u in parallel if u["deselect"]}
        for entry in release_only.RELEASE_ONLY:
            file = entry.split("::", 1)[0]
            if file in runner.SERIAL or file in runner.WHOLE:
                assert entry not in nodes and file not in split
            else:
                assert entry in nodes and file in split


def test_counts_are_read_from_the_summary_line(tmp_path):
    log = tmp_path / "x.log"
    log.write_text("....\n= 1 failed, 3 passed, 2 skipped, 10 subtests passed, 1 error in 2.10s =\n")
    assert runner.counts_of(log) == {"failed": 1, "passed": 3, "skipped": 2, "subtests passed": 10, "errors": 1}
