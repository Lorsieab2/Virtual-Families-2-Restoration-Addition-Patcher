param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputs = Join-Path $root "outputs"
$patcher = Join-Path $root "work\patch_mobile_furniture_pack.py"
$builder = Join-Path $root "work\build_b119.bat"
$validator = Join-Path $root "work\validate_b153_debugger_fallthrough.py"
$previous = Join-Path $outputs "VF2-Mobile-Furniture-With-Island-Events-B152-island_events_cheat_upgrades_holiday_ornaments_behavior_patches"
$out = Join-Path $outputs "B153-Debugger-Fallthrough-Fix-Test"
$exeName = "Virtual Families 2 - B153 Debugger Fallthrough Fix Test.exe"

if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = $env:VF2_PYTHON
}
if ([string]::IsNullOrWhiteSpace($Python) -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Pass -Python with a workspace-usable Python 3 executable."
}
foreach ($required in @($patcher, $builder, $validator)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required source missing: $required"
    }
}
if (-not (Test-Path -LiteralPath $previous -PathType Container)) {
    throw "B152 all-patches base missing: $previous"
}

New-Item -ItemType Directory -Path $out -Force | Out-Null
$env:VF2_PATCH_OUT = $out
$env:VF2_BUILD_OUT = $out
$env:VF2_OUTPUT_EXE = $exeName
$env:VF2_PREVIOUS_BUILD_DIR = $previous
$env:VF2_ENABLE_ISLAND_EVENTS = "1"
$env:VF2_ENABLE_CHEAT_UPGRADES = "1"
$env:VF2_ENABLE_HOLIDAY_ORNAMENTS = "1"
$env:VF2_ENABLE_BEHAVIOR_PATCHES = "1"
$env:VF2_ENABLE_DEBUGGER_FEATURES = "1"

$patchLog = Join-Path $out "debugger-fallthrough-patch.log"
$buildLog = Join-Path $out "debugger-fallthrough-build.log"
& $Python $patcher *> $patchLog
if ($LASTEXITCODE -ne 0) {
    Get-Content -LiteralPath $patchLog -Tail 100
    throw "Debugger patch generation failed with exit code $LASTEXITCODE"
}
& cmd.exe /d /c $builder *> $buildLog
if ($LASTEXITCODE -ne 0) {
    Get-Content -LiteralPath $buildLog -Tail 120
    throw "Debugger build failed with exit code $LASTEXITCODE"
}

$exe = Join-Path $out $exeName
$manifest = Join-Path $out "patch-manifest.json"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Debugger test executable missing: $exe"
}
if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
    throw "Debugger manifest missing: $manifest"
}
$manifestData = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestData.debug_features.developer_keys.status -notmatch "F5-gated") {
    throw "Debugger feature manifest is not F5-gated/enabled."
}
$report = Join-Path $out "debugger-fallthrough-validation.json"
& $Python $validator --exe $exe --manifest $manifest --output $report
if ($LASTEXITCODE -ne 0) {
    throw "Debugger fallthrough validation failed with exit code $LASTEXITCODE"
}
Write-Host "Validated corrected debugger test: $exe"
