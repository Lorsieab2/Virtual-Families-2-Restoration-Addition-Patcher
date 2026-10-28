# Run the independent release steps at the same time instead of one after another.
#
#   powershell -File work\release_parallel.ps1 -Python <python.exe> -ReleaseConfig data\vf2\build-matrix-release-bNNN.json `
#       -Worktrees C:\vf2w\bNNN-m1,C:\vf2w\bNNN-m2,C:\vf2w\bNNN-m3 -Vcvars32 <vcvars32.bat> `
#       -B200CoreExe <B200 core exe> -B201CoreExe <B201 core exe> [-Workers 12] [-SkipMatrix]
#
# Run it from the release worktree (the checkout the bundle is exported from). What runs, and why in this order:
#
#   at once:  the matrix, split over -Worktrees (work\build_matrix_parallel.ps1)
#             an early full test run here (scripts\run_tests_parallel.py --release), without the matrix: the
#               tests that need a matrix executable skip, everything else reports while the matrix builds
#             (and whatever the operator does by hand meanwhile: release notes, README, matrix manifest)
#   then:     the matrix is collected into this checkout (only now: tests glob outputs\ for matrix folders
#               and manifests, so folders arriving during the early run would be read half-copied), and
#             the release test run, --release, with VF2_KIDS_EXE and VF2_B200_MATRIX_GLOB pointing at the new
#               matrix, so the tests that need it run. This is the run the release gate reads.
#   last:     the companion DLLs (runtime\native\build_b200time.bat, build_b200kids.bat, build_b200history.bat,
#               build_b200outfits.bat, build_b200refresh.bat). Last, because tests\test_b200_time_controls.py,
#               test_b200_up_to_28_children.py, test_b200_family_history.py, test_b200_outfit_pictures.py and
#               test_b200_store_refresh.py
#               rebuild the same runtime\build files; building the release DLLs after them means runtime\build
#               holds the build this script made on purpose.
#
# Exporting the bundle and the release gate stay manual steps after this script. It changes nothing about what
# is built: the matrix is work\build_matrix.ps1 with the same toggles, and the DLLs are the same batch files.
# Output: %TEMP%\vf2-release-parallel-<time>\ (test summaries and logs; not under outputs\, which tests read).
param(
    [Parameter(Mandatory = $true)] [string]$Python,
    [Parameter(Mandatory = $true)] [string]$ReleaseConfig,
    [Parameter(Mandatory = $true)] [string[]]$Worktrees,
    [Parameter(Mandatory = $true)] [string]$Vcvars32,
    [string]$B200CoreExe,
    [string]$B201CoreExe,
    [string]$MatrixConfig = "data\vf2\build-matrix-toggles.json",
    [int]$Workers = 12,
    [switch]$SkipMatrix
)

$ErrorActionPreference = "Stop"
$Worktrees = @($Worktrees | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$release = Get-Content -LiteralPath $ReleaseConfig -Raw | ConvertFrom-Json
$prefix = $release.output_prefix
$exeName = $release.exe_name
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path ([IO.Path]::GetTempPath()) "vf2-release-parallel-$stamp"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
$ps = Join-Path $PSHOME "powershell.exe"

$env:VF2_VCVARS32 = $Vcvars32
if ($B200CoreExe) { $env:VF2_B200_CORE_EXE = $B200CoreExe }
if ($B201CoreExe) { $env:VF2_B201_CORE_EXE = $B201CoreExe }

$matrix = $null
if (-not $SkipMatrix) {
    $matrixArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$(Join-Path $root 'work\build_matrix_parallel.ps1')`"",
                    "-Python", "`"$Python`"", "-MatrixConfig", "`"$MatrixConfig`"", "-ReleaseConfig", "`"$ReleaseConfig`"",
                    "-Worktrees", "`"$($Worktrees -join ',')`"")
    $matrix = Start-Process $ps -ArgumentList $matrixArgs -WorkingDirectory $root -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $runDir "matrix.log") -RedirectStandardError (Join-Path $runDir "matrix.err.log")
    $null = $matrix.Handle      # keeps the handle open, or ExitCode is empty after the process exits
    Write-Host "matrix: started (log $runDir\matrix.log)"
}

# The early run: no matrix yet, so the tests that need one skip rather than read a half-built folder.
$saved = @{ kids = $env:VF2_KIDS_EXE; glob = $env:VF2_B200_MATRIX_GLOB; refresh = $env:VF2_REFRESH_EXE }
Remove-Item Env:VF2_KIDS_EXE, Env:VF2_B200_MATRIX_GLOB, Env:VF2_REFRESH_EXE -ErrorAction SilentlyContinue
& $Python scripts\run_tests_parallel.py --release --workers $Workers --out (Join-Path $runDir "tests-early")
$early = $LASTEXITCODE
Write-Host "early test run: exit $early"

if ($matrix) {
    $matrix.WaitForExit()
    if ($matrix.ExitCode -ne 0) { throw "The matrix failed (exit $($matrix.ExitCode)); see $runDir\matrix.log and matrix.err.log." }
    # Collected only now, after the early run: tests here glob outputs\ for matrix folders and the newest
    # manifest, so folders arriving mid-run would be read half-copied.
    & $ps -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "work\build_matrix_parallel.ps1") -Python $Python `
        -MatrixConfig $MatrixConfig -ReleaseConfig $ReleaseConfig -Worktrees ($Worktrees -join ',') -CollectOnly -CollectInto $root
    if ($LASTEXITCODE -ne 0) { throw "Collecting the matrix failed." }
    Write-Host "matrix: built and collected"
}
$env:VF2_KIDS_EXE = Join-Path $root "outputs\$prefix-core\$exeName"
$env:VF2_B200_MATRIX_GLOB = Join-Path $root "outputs\$prefix-*\*.exe"
# The R Refreshes the Store tests run the new core executable's own .vf2rfsh loader and .vf2flea byte.
$env:VF2_REFRESH_EXE = $env:VF2_KIDS_EXE
if (-not (Test-Path -LiteralPath $env:VF2_KIDS_EXE)) { throw "No core executable at $env:VF2_KIDS_EXE" }
& $Python scripts\run_tests_parallel.py --release --workers $Workers --out (Join-Path $runDir "tests-release")
$gate = $LASTEXITCODE
if ($null -ne $saved.kids) { $env:VF2_KIDS_EXE = $saved.kids }
if ($null -ne $saved.glob) { $env:VF2_B200_MATRIX_GLOB = $saved.glob }
if ($null -ne $saved.refresh) { $env:VF2_REFRESH_EXE = $saved.refresh } else { Remove-Item Env:VF2_REFRESH_EXE -ErrorAction SilentlyContinue }
if ($gate -ne 0) { throw "The release test run still fails alone; see $runDir\tests-release\summary.txt. DLLs not built." }

foreach ($bat in @("build_b200time.bat", "build_b200kids.bat", "build_b200history.bat", "build_b200outfits.bat", "build_b200refresh.bat")) {
    & cmd.exe /d /c "`"$(Join-Path $root "runtime\native\$bat")`"" > (Join-Path $runDir "$bat.log") 2>&1
    if ($LASTEXITCODE -ne 0) { throw "$bat failed; see $runDir\$bat.log" }
}
Get-ChildItem (Join-Path $root "runtime\build") -Filter "*.dll" |
    ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash, $_.Name } |
    Tee-Object -FilePath (Join-Path $runDir "dlls.txt")
Write-Host "Done. Early run exit $early; release run passed; DLLs built. Next: export the bundle and run the release gate."
