"""Release-only tests: the slow ones an ordinary run skips and the run before a release includes.

Every test below took 15 s or more in a full serial run of both suites (2026-10-23, B202 main, pytest's JUnit
times); together they were about 1,580 s of a 2,600 s run, and seven of them sit in one file. One more test
took 120 s, work/test_special_upgrades_release_parity.py's late-icons check, and is NOT here: skipping it only
moves the same time to the next test in that class, which builds the same cached manifest, so it would hide a
test and save nothing. An ordinary run skips the tests below and says why. The run before a release must
include them:

    python scripts/run_tests_parallel.py --release        (or: pytest --release, or VF2_RELEASE=1)

tests/conftest.py and work/conftest.py load this module, so the rule is the same in both suites and in CI.
Entries are "<suite>/<file>::<rest of the pytest node id>", independent of the folder pytest runs from;
tests/test_parallel_runner.py checks that every entry names a real test.

scripts/run_tests_parallel.py --release runs each entry in its own process beside the rest (except in the
files it keeps whole), so a release run is not held up by them one after another. It sets VF2_RELEASE_ONLY=
deselect for the process that runs the rest of such a file, so those tests are left out there rather than run
twice or reported as skipped.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

RELEASE_ONLY = (
    "tests/test_b200_time_controls.py::test_every_mutation_is_caught",
    "work/test_patch_mobile_furniture_pack.py::MobileRenovationArtTests::"
    "test_ai_bathroom2_rows_work_without_first_bathroom_toggle",
    "work/test_patch_mobile_furniture_pack.py::MobileRenovationArtTests::"
    "test_house_renovation_rows_match_pinned_price_lock_and_text_contract",
    "work/test_patch_mobile_furniture_pack.py::TextFixStringManagerTests::"
    "test_all_custom_achievement_strings_are_exact_and_stable",
    "work/test_patch_mobile_furniture_pack.py::TextFixStringManagerTests::"
    "test_power_failure_text_is_stock_without_island_events",
    "work/test_patch_mobile_furniture_pack.py::TextFixStringManagerTests::"
    "test_power_failure_spoiled_text_is_retargeted_in_island_event_builds",
    "work/test_patch_mobile_furniture_pack.py::TextFixStringManagerTests::"
    "test_holiday_collection_screen_uses_ornament_only_strings",
    "work/test_patch_mobile_furniture_pack.py::TextFixStringManagerTests::"
    "test_text_fixes_retarget_existing_stock_strings",
    "work/test_transparent_furniture_drop.py::TheCompiledObject::"
    "test_every_undefined_external_is_one_the_stock_objects_export",
    "work/test_generated_cpp_compiles.py::TestEveryGeneratedUnitCompiles::test_each_file_compiles",
)
RELEASE_SKIP_REASON = "release-only (slow): run with --release or VF2_RELEASE=1"


def key(item) -> str:
    """The RELEASE_ONLY form of a collected item's node id, whatever folder pytest was started from."""
    path = Path(str(item.path)).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = path.name
    rest = item.nodeid.split("::", 1)[1] if "::" in item.nodeid else ""
    return f"{name}::{rest}"


def pytest_addoption(parser):
    try:
        parser.addoption("--release", action="store_true", default=False,
                         help="also run the slow release-only tests (scripts/release_only.py RELEASE_ONLY)")
    except ValueError:      # both conftests loaded in one session: the option is already there
        pass


def release_run(config) -> bool:
    return bool(config.getoption("--release")) or os.environ.get("VF2_RELEASE") == "1"


def pytest_collection_modifyitems(config, items):
    slow = set(RELEASE_ONLY)
    if os.environ.get("VF2_RELEASE_ONLY") == "deselect":
        dropped = [item for item in items if key(item) in slow]
        if dropped:
            config.hook.pytest_deselected(items=dropped)
            items[:] = [item for item in items if key(item) not in slow]
        return
    if release_run(config):
        return
    skip = __import__("pytest").mark.skip(reason=RELEASE_SKIP_REASON)
    for item in items:
        if key(item) in slow:
            item.add_marker(skip)
