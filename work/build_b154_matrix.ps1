param(
    [string]$Python = "",
    [ValidateRange(0, 15)]
    [int]$StartMask = 0
)

$ErrorActionPreference = "Stop"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputs = Join-Path $root "outputs"
$patcher = Join-Path $root "work\patch_mobile_furniture_pack.py"
$builder = Join-Path $root "work\build_b119.bat"
$holidayValidator = Join-Path $root "work\validate_b153_holiday_collection.py"
$runtimeValidator = Join-Path $root "work\validate_b153_runtime_flags.py"
$debuggerValidator = Join-Path $root "work\validate_b153_debugger_fallthrough.py"
$exeName = "Virtual Families 2 - Additive Mobile Furniture Pack.exe"

$pythonArgs = @()
if ([string]::IsNullOrWhiteSpace($Python) -and -not [string]::IsNullOrWhiteSpace($env:VF2_PYTHON)) {
    $Python = $env:VF2_PYTHON
}
if (-not [string]::IsNullOrWhiteSpace($Python)) {
    if (Test-Path -LiteralPath $Python -PathType Leaf) {
        $pythonExe = (Resolve-Path -LiteralPath $Python).Path
    }
    else {
        $pythonCommand = Get-Command $Python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $pythonCommand) {
            throw "Python runtime not found: $Python"
        }
        $pythonExe = $pythonCommand.Source
    }
}
else {
    $pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $pythonCommand) {
        $pythonCommand = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $pythonCommand) {
            $pythonArgs = @("-3")
        }
    }
    if ($null -eq $pythonCommand) {
        throw "Python 3 was not found. Pass -Python, or set VF2_PYTHON to a Python executable."
    }
    $pythonExe = $pythonCommand.Source
}
if (-not (Test-Path -LiteralPath $patcher -PathType Leaf)) {
    throw "Patcher source not found: $patcher"
}
if (-not (Test-Path -LiteralPath $holidayValidator -PathType Leaf)) {
    throw "B153 linked Holiday validator not found: $holidayValidator"
}
if (-not (Test-Path -LiteralPath $runtimeValidator -PathType Leaf)) {
    throw "B153 runtime validator not found: $runtimeValidator"
}
if (-not (Test-Path -LiteralPath $debuggerValidator -PathType Leaf)) {
    throw "B153 debugger validator not found: $debuggerValidator"
}

Push-Location $root
try {
    for ($mask = $StartMask; $mask -lt 16; ++$mask) {
        $island = (($mask -band 1) -ne 0)
        $cheat = (($mask -band 2) -ne 0)
        $holiday = (($mask -band 4) -ne 0)
        $behavior = (($mask -band 8) -ne 0)

        $parts = @()
        if ($island) { $parts += "island_events" }
        if ($cheat) { $parts += "cheat_upgrades" }
        if ($holiday) { $parts += "holiday_ornaments" }
        if ($behavior) { $parts += "behavior_patches" }
        $variant = if ($parts.Count) { $parts -join "_" } else { "core" }

        $previous = Join-Path $outputs "VF2-Mobile-Furniture-With-Island-Events-B153-$variant"
        $out = Join-Path $outputs "VF2-Mobile-Furniture-With-Island-Events-B154-$variant"
        if (-not (Test-Path -LiteralPath $previous -PathType Container)) {
            throw "Missing B152 base for ${variant}: $previous"
        }
        New-Item -ItemType Directory -Path $out -Force | Out-Null

        $env:VF2_PATCH_OUT = $out
        $env:VF2_BUILD_OUT = $out
        $env:VF2_OUTPUT_EXE = $exeName
        $env:VF2_PREVIOUS_BUILD_DIR = $previous
        $env:VF2_ENABLE_ISLAND_EVENTS = if ($island) { "1" } else { "0" }
        $env:VF2_ENABLE_CHEAT_UPGRADES = if ($cheat) { "1" } else { "0" }
        $env:VF2_ENABLE_HOLIDAY_ORNAMENTS = if ($holiday) { "1" } else { "0" }
        $env:VF2_ENABLE_BEHAVIOR_PATCHES = if ($behavior) { "1" } else { "0" }
        $env:VF2_ENABLE_DEBUGGER_FEATURES = "1"

        $patchLog = Join-Path $out "b154-patch.log"
        $buildLog = Join-Path $out "b154-build.log"
        Write-Host "[$($mask + 1)/16] Generating $variant"
        & $pythonExe @pythonArgs $patcher *> $patchLog
        if ($LASTEXITCODE -ne 0) {
            Get-Content -LiteralPath $patchLog -Tail 80
            throw "Patch generation failed for $variant with exit code $LASTEXITCODE"
        }

        Write-Host "[$($mask + 1)/16] Compiling $variant"
        & cmd.exe /d /c $builder *> $buildLog
        if ($LASTEXITCODE -ne 0) {
            Get-Content -LiteralPath $buildLog -Tail 120
            throw "Build failed for $variant with exit code $LASTEXITCODE"
        }

        $exe = Join-Path $out $exeName
        $manifest = Join-Path $out "patch-manifest.json"
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
            throw "Built EXE missing for $variant"
        }
        if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
            throw "Patch manifest missing for $variant"
        }
        $manifestData = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
        if ($manifestData.BehaviorPatchesGate.enabled -ne $behavior) {
            throw "Behavior gate mismatch in $variant manifest"
        }
        if ($manifestData.native_array_contract.island_events.enabled -ne $island) {
            throw "Island Events gate mismatch in $variant manifest"
        }
        if ($manifestData.ScrollingStoreScene.price_multiplier.enabled -ne $cheat) {
            throw "Cheat Upgrades gate mismatch in $variant manifest"
        }
        if ($manifestData.native_array_contract.holiday_ornaments.enabled -ne $holiday) {
            throw "Holiday gate mismatch in $variant manifest"
        }
        $debuggerReport = Join-Path $out "b154-debugger-validation.json"
        & $pythonExe @pythonArgs $debuggerValidator --exe $exe --manifest $manifest --output $debuggerReport *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Debugger validation failed for $variant with exit code $LASTEXITCODE"
        }
        Write-Host "[$($mask + 1)/16] Verified $variant ($((Get-Item -LiteralPath $exe).Length) bytes)"
    }
}
finally {
    Pop-Location
}

Write-Host "Running B154 linked Holiday positive/negative validation"
& $pythonExe @pythonArgs $holidayValidator
if ($LASTEXITCODE -ne 0) {
    throw "B154 linked Holiday validation failed with exit code $LASTEXITCODE"
}

Write-Host "Running B154 linked runtime-flag validation"
$runtimeReport = Join-Path $outputs "B154-Runtime-Flag-Validation.json"
& $pythonExe @pythonArgs $runtimeValidator --build-label B154 --output $runtimeReport
if ($LASTEXITCODE -ne 0) {
    throw "B154 linked runtime-flag validation failed with exit code $LASTEXITCODE"
}

Write-Host "B154 16-state executable matrix and linked validation completed successfully."
