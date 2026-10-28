"""Run both test suites (tests/ and work/) in parallel: one pytest process per test file, several at a time.

The same approach as the Virtual Villagers Fun Patcher's scripts/run_tests_parallel.py. Run one file after
another, the two suites took 43 minutes on the B202 main; split over 12 workers they take a few minutes.

    python scripts/run_tests_parallel.py [--release] [--workers 12] [--suite all|tests|work] [--out DIR]
    python scripts/run_tests_parallel.py --list [--suite tests]       # print the files a run covers

How each file runs
  * in its own process: `python -m pytest -q -rfEs -p no:cacheprovider --basetemp=<short> --junitxml=...`.
    tests/ and work/ hold files with the same names (test_offline_vf2_patcher.py and others), so the two
    suites can never share one pytest session anyway.
  * from the folder it is normally run from: tests/ files from the repository root (as CI runs them), work/
    files from work/ (as AGENTS.md says), with that folder on PYTHONPATH. Every other environment variable
    (VF2_B200_CORE_EXE, VF2_B201_CORE_EXE, VF2_KIDS_EXE, VF2_REFRESH_EXE, VF2_B200_MATRIX_GLOB, VF2_VCVARS32, VF2_VANILLA_EXE,
    VF2_VERIFY_RELEASE, ...) passes through unchanged, so a test that needs one skips exactly as it would alone.
  * with a SHORT --basetemp under %TEMP% (deep temp paths pass the 260-character limit), one per process.

Shared state (measured: a serial run that recorded every path in the checkout each file changed)
  SERIAL files write fixed paths that other files read; they run one at a time AFTER the parallel pass, with
  nothing beside them. WHOLE files rebuild fixed files of their own from several tests, so they are never
  split into more than one process. Every name in both lists must be a real file (tests/test_parallel_runner.py).

Release-only tests (scripts/release_only.py)
  Without --release they skip and say so. With --release each one outside SERIAL and WHOLE runs in its own
  process beside the rest, and the process for the rest of its file leaves it out (VF2_RELEASE_ONLY=deselect),
  so every test runs exactly once. The run before a release must use --release.

Results
  Every process that fails is run again on its own; only failures that persist alone count. The summary
  (totals, what failed in the first pass, what still fails alone, the slowest units) is printed and written to
  <out>/summary.txt, with a log and a JUnit XML per process beside it and results.json holding the per-file
  counts. Exit status 1 when anything still fails alone, else 0.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SUITES = ("tests", "work")

SERIAL = (
    # sync_behavior_assets() rewrites the lounger .fmap files in the generator's default output folder,
    # outputs/VF2-Mobile-Additive-Furniture-Pack/Assets, which other work/ files read.
    "work/test_spa_lounger_hotspot.py",
)
WHOLE = (
    # Each rebuilds runtime/build/vf2time_b200*.dll (resp. vf2kids_b200*.dll) in a shared fixture; two
    # processes of one file would build the same DLL at the same moment. The two files build different DLLs,
    # and no other test reads runtime/build, so each file as a whole runs in the parallel pass.
    "tests/test_b200_time_controls.py",
    "tests/test_b200_up_to_28_children.py",
    "tests/test_b200_family_history.py",
    "tests/test_b200_outfit_pictures.py",
    "tests/test_b200_store_refresh.py",
)

COUNT = re.compile(r"(\d+) (subtests )?(passed|failed|skipped|errors?|xfailed|xpassed|deselected)")


def _release_only() -> tuple:
    spec = importlib.util.spec_from_file_location("vf2_release_only", REPO / "scripts" / "release_only.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RELEASE_ONLY


RELEASE_ONLY = _release_only()


def suite_files(suite: str) -> list[Path]:
    names = SUITES if suite == "all" else (suite,)
    found: list[Path] = []
    for name in names:
        found += sorted((REPO / name).glob("test_*.py"))
    return found


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def units(files: list[Path], release: bool) -> tuple[list[dict], list[dict]]:
    """(parallel units, serial units). A unit is one pytest process: a whole file, the rest of a file, or one
    release-only test."""
    parallel, serial = [], []
    for path in files:
        name = rel(path)
        split = [n for n in RELEASE_ONLY if n.split("::", 1)[0] == name] if release else []
        if name in SERIAL:
            serial.append({"file": name, "node": None, "deselect": False})
        elif split and name not in WHOLE:
            parallel.append({"file": name, "node": None, "deselect": True})
            parallel += [{"file": name, "node": n.split("::", 1)[1], "deselect": False} for n in split]
        else:
            parallel.append({"file": name, "node": None, "deselect": False})
    # Longest first, so the slowest units start at once: the WHOLE files (the two longest, measured) and the
    # release-only tests, then the rest by file size.
    parallel.sort(key=lambda u: (u["node"] is None and u["file"] not in WHOLE, -(REPO / u["file"]).stat().st_size))
    return parallel, serial


def label(unit: dict) -> str:
    return unit["file"] + (f"::{unit['node']}" if unit["node"] else "")


def counts_of(log: Path) -> dict:
    """The counts from pytest's final summary line ("3 passed, 1 skipped, 10 subtests passed in 2.1s")."""
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        if " in " in line and COUNT.search(line):
            found: dict = {}
            for number, sub, key in COUNT.findall(line):
                key = ("subtests " if sub else "") + ("errors" if key == "error" else key)
                found[key] = found.get(key, 0) + int(number)
            return found
    return {}


def run_one(unit: dict, tag: str, out: Path, short: Path, release: bool) -> dict:
    test = REPO / unit["file"]
    suite = test.parent.name
    cwd = REPO if suite == "tests" else test.parent
    ident = f"{zlib.crc32(label(unit).encode()):08x}"
    stem = f"{tag}_{suite}_{test.stem}" + (f"_{ident}" if unit["node"] else "")
    log, xml = out / f"{stem}.log", out / f"{stem}.xml"
    basetemp = short / f"{tag[0]}{ident}"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(test.parent), env.get("PYTHONPATH", "")) if p)
    env.pop("VF2_RELEASE_ONLY", None)
    if unit["deselect"]:
        env["VF2_RELEASE_ONLY"] = "deselect"
    target = os.path.relpath(test, cwd) + (f"::{unit['node']}" if unit["node"] else "")
    command = [sys.executable, "-m", "pytest", "-q", "-rfEs", "-p", "no:cacheprovider",
               f"--basetemp={basetemp}", f"--junitxml={xml}", target]
    if release:
        command.append("--release")
    start = time.time()
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        fh.write(f"# cwd: {cwd}\n# {' '.join(command)}\n")
        fh.flush()
        rc = subprocess.call(command, cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT)
    shutil.rmtree(basetemp, ignore_errors=True)
    return dict(unit, unit=label(unit), rc=rc, counts=counts_of(log), seconds=round(time.time() - start, 1),
                log=log.name)


def failed(result: dict) -> bool:
    return result["rc"] not in (0, 5)          # 5: no tests collected


def total(results: list) -> dict:
    counts: dict = {}
    for result in results:
        for key, value in result["counts"].items():
            counts[key] = counts.get(key, 0) + value
    counts.pop("deselected", None)             # the release-only tests a split file leaves to their own process
    return dict(sorted(counts.items()))


def per_file(results: list) -> dict:
    files: dict = {}
    for result in results:
        files.setdefault(result["file"], []).append(result)
    return {name: {"rc": max(r["rc"] for r in rs), "counts": total(rs)} for name, rs in sorted(files.items())}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "vf2-parallel-tests")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--suite", choices=("all",) + SUITES, default="all")
    parser.add_argument("--release", action="store_true", help="also run the release-only tests")
    parser.add_argument("--list", action="store_true", help="print the files and exit")
    args = parser.parse_args(argv)

    files = suite_files(args.suite)
    if args.list:
        print("\n".join(rel(f) for f in files))
        return 0
    parallel, serial = units(files, args.release)

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    short = Path(tempfile.gettempdir()) / "vf2p"
    short.mkdir(exist_ok=True)

    began = time.time()
    with cf.ThreadPoolExecutor(max(1, args.workers)) as pool:
        first = list(pool.map(lambda u: run_one(u, "par", out, short, args.release), parallel))
    first += [run_one(u, "ser", out, short, args.release) for u in serial]
    retry = [r for r in first if failed(r)]
    again = [run_one(r, "solo", out, short, args.release) for r in retry]
    still = [r["unit"] for r in again if failed(r)]
    wall = time.time() - began

    slowest = sorted(first, key=lambda r: -r["seconds"])[:5]
    lines = [
        f"files: {len(files)}  processes: {len(parallel)} parallel + {len(serial)} serial  workers: {args.workers}  "
        f"release: {args.release}  wall: {wall:.0f} s",
        f"totals: {total(first)}",
        f"failed in the first pass: {len(retry)}: {', '.join(r['unit'] for r in retry) or 'none'}",
        f"run again alone: {total(again)}",
        f"STILL FAILING ALONE: {len(still)}: {', '.join(still) or 'none'}",
        "slowest: " + ", ".join(f"{r['unit']} {r['seconds']:.0f} s" for r in slowest),
    ]
    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "results.json").write_text(json.dumps({"wall": round(wall), "files": per_file(first),
                                                  "first": first, "again": again}, indent=1), encoding="utf-8")
    print("\n".join(lines))
    print(f"logs: {out}")
    return 1 if still else 0


if __name__ == "__main__":
    raise SystemExit(main())
