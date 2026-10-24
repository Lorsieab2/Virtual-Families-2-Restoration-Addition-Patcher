# Running the tests and the release steps in parallel

## The test suites

```powershell
python scripts\run_tests_parallel.py              # ordinary run: release-only tests skip
python scripts\run_tests_parallel.py --release    # the run before a release (the release gate reads this one)
python scripts\run_tests_parallel.py --suite tests --workers 4 --out C:\Temp\t
python scripts\run_tests_parallel.py --list       # the files a run covers
```

The runner covers both suites, `tests\` and `work\`. It starts one pytest process per test file, 12 at a
time (`--workers`), each from the folder that file is normally run from (`tests\` files from the repository
root, `work\` files from `work\`), with that folder on `PYTHONPATH`, its own short `--basetemp` under
`%TEMP%` (deep temp paths pass the 260-character limit) and `-p no:cacheprovider`. Every file that fails is
run again on its own, and only failures that persist alone count. The summary is printed and written to
`<out>\summary.txt` (default `%TEMP%\vf2-parallel-tests`), beside one log and one JUnit XML per process and
`results.json` (per-file counts). The exit status is 1 when anything still fails alone.

Environment variables pass straight through, so a test that needs one skips exactly as it would alone. A
release run sets the ones the release gate needs before starting the runner: `VF2_VCVARS32`,
`VF2_B200_CORE_EXE`, `VF2_B201_CORE_EXE`, `VF2_KIDS_EXE` (the new matrix's core executable),
`VF2_B200_MATRIX_GLOB` (a glob over the new matrix's executables), and any of `VF2_VANILLA_EXE`,
`VF2_VERIFY_RELEASE`, `VF2_LINK_TEST` that apply. As before, the `work\` suite needs the gitignored build
inputs (`work\vanilla_runtime_payload`, `work\desktop_obj_files`, `outputs\`, ...) in the checkout it runs in.

Measured on the B202 main (24 cores, all inputs present, every test passing):

| run | wall time | passed | skipped | subtests passed |
| --- | --- | --- | --- | --- |
| serial: `pytest tests/ --release`, then `pytest test_*.py --release` in `work\` | 2,450 s (41 min) | 1,938 | 27 | 8,467 |
| parallel, `--release` | 544 s (523 s in an earlier run) | 1,937 | 28 | 8,467 |
| parallel, ordinary (release-only tests skip) | 253 s to 423 s | 1,925 | 40 | 8,457 |

Per file, the serial and parallel `--release` runs agree on every file's passes, failures and skips except:
the Tk skips below; one test in `tests\test_offline_vf2_patcher.py` that skips when run on its own
("export_offline_patch_bundle is a build tool and is not part of the shipped tree; the work/ copy of this
suite covers it") and runs in the one-process serial run only because an earlier file in that process put
`work\` on `sys.path` (it runs in `work\test_offline_vf2_patcher.py` either way); and a counting difference in
`work\test_mobile_sound_route_toggle_contract.py`, where pytest's summary counts four skipped subtests that the
JUnit file records as one test. The wall time of a parallel run is set by its longest file,
`tests\test_b200_time_controls.py` (350 s alone, more beside eleven other workers), and varies with the load
on the machine.

### Shared state

A serial run that recorded every path in the checkout each test file changed found these, and the runner
handles them as follows (`SERIAL` and `WHOLE` in the script):

- `work\test_spa_lounger_hotspot.py` rewrites the lounger `.fmap` files in the generator's default output
  folder, `outputs\VF2-Mobile-Additive-Furniture-Pack\Assets`, which other `work\` files read. It is in
  `SERIAL`: it runs alone, after the parallel pass.
- `tests\test_b200_time_controls.py` and `tests\test_b200_up_to_28_children.py` rebuild
  `runtime\build\vf2time_b200*.dll` and `runtime\build\vf2kids_b200*.dll` in a shared fixture. Nothing else
  reads `runtime\build`, and the two build different files, so each runs whole in the parallel pass; they are
  in `WHOLE`, so the runner never splits either over two processes (two builds of one DLL at once).
- The two GUI test files write `patcher_local_settings.json` beside their own GUI module (`src\` and
  `work\`); nothing else reads either file.
- Many `work\` tests read whatever the generator last wrote (`work\patched_mobile_furniture_pack_objs`,
  `outputs\VF2-Mobile-Additive-Furniture-Pack`). No test writes those, so in parallel they all read the same
  files they read one at a time. Run the generator before the suite, not during it.

`tests\test_parallel_runner.py` checks that every name in these lists is a real file. The GUI tests skip one
or two tests at random with "no display available for Tk" (`tk.Tk()` sometimes fails on this machine); that
happens in serial runs too and is the only difference measured between a serial and a parallel run.

### Release-only tests

The tests in `scripts\release_only.py` (`RELEASE_ONLY`) each took 15 s or more; together they were about
1,580 s of the 2,600 s serial run. An ordinary run (`pytest`, or the runner without `--release`) skips them
with the reason "release-only (slow): run with --release or VF2_RELEASE=1". The run before a release must
use `--release` (or `VF2_RELEASE=1`). With `--release` the runner gives each of them its own process beside
the rest, so they do not run one after another. `tests\conftest.py` and `work\conftest.py` both load the
list, and `tests\test_parallel_runner.py` checks that every entry names a real test.

### CI

`.github/workflows/tests.yml` stays one job: the test step takes about 55 s of a 1.5-minute run, so
splitting it over runners would spend more on runner setup than it saves. It runs
`python -m pytest tests/ --release`, which is the same file list as
`python scripts\run_tests_parallel.py --list --suite tests`. CI has no game files and no Visual Studio, so
every test that needs them skips with its reason (`-rs`). `--release` there means a release-only test is never
dropped from CI; on the runner those skip for want of the binaries anyway.

## The release steps

The variant matrix is the long step, and one checkout can build one variant at a time (the generator writes
`work\patched_mobile_furniture_pack_objs`), so it is split over worktrees of the release commit, as B202 was
built by hand:

```powershell
git worktree add --detach C:\vf2w\bNNN-m1 <commit>     # and m2, m3; copy work\vanilla_runtime_payload and
                                                       # the seed folders the release config names into each
powershell -File work\build_matrix_parallel.ps1 -Python <python.exe> `
    -MatrixConfig data\vf2\build-matrix-toggles.json -ReleaseConfig data\vf2\build-matrix-release-bNNN.json `
    -Worktrees C:\vf2w\bNNN-m1,C:\vf2w\bNNN-m2,C:\vf2w\bNNN-m3 -CollectInto C:\vf2w\bNNN-release
```

It checks every worktree is at this checkout's commit with no tracked changes, deals the variants out in
matrix order (variant i to part i mod N), runs the unchanged `work\build_matrix.ps1` in each worktree at once
with a matrix file holding only that part's variants (toggles copied as they are), renames each part's summary
and logs to `-summary-mK.json` / `-logs-mK`, and with `-CollectInto` copies every variant folder into the
release checkout's `outputs\` and checks all 32 arrived with distinct hashes. `-PlanOnly` prints the split
and builds nothing; `-CollectOnly` only collects. Checked so far: `-PlanOnly` on the 32-variant matrix (the
three parts hold exactly the 32 variants, toggles unchanged), and a real two-variant build (core and
behavior_patches, seeded from B202) over two worktrees, both linked and collected with distinct hashes in
8 minutes. A full 32-variant release build with it has not been run yet. Each worktree needs every seed folder
its part's variants name; the generator fails without them (`missing required runtime file: wc.dat`).

`work\release_parallel.ps1` runs the independent steps together, from the release worktree:

1. at once: the matrix in the part worktrees, and an early `run_tests_parallel.py --release` in the release
   worktree (the tests that need a matrix executable skip; everything else reports while the matrix builds).
   Release notes, the README and the matrix manifest can be written meanwhile.
2. then: collect the matrix (only now, because tests glob `outputs\` for matrix folders and manifests), and
   the release test run, `--release`, with `VF2_KIDS_EXE` and `VF2_B200_MATRIX_GLOB` set to the new matrix.
3. last: the two companion DLLs (`runtime\native\build_b200time.bat`, `build_b200kids.bat`), because the two
   B200 test files rebuild the same `runtime\build` files.

Exporting the bundle and the release gate stay manual steps after it. Neither script changes what is built.
