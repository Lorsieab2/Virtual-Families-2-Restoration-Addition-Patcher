param(
    [string]$Python = "",
    [ValidateRange(0, 15)]
    [int]$StartMask = 0
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputs = Join-Path $root "outputs"
$patcher = Join-Path $root "work\patch_mobile_furniture_pack.py"
$builder = Join-Path $root "work\build_b119.bat"
$validator = Join-Path $root "work\validate_b151_holiday_collection.py"
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
        $pythonCommand = Get-Command $Python -CommandType Application -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) {
            throw "Python runtime not found: $Python"
        }
        $pythonExe = $pythonCommand.Source
    }
}
else {
    $pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        $pythonCommand = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
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
if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) {
    throw "B151 linked validator not found: $validator"
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

        $previous = Join-Path $outputs "VF2-Mobile-Furniture-With-Island-Events-B150-$variant"
        $out = Join-Path $outputs "VF2-Mobile-Furniture-With-Island-Events-B151-$variant"
        if (-not (Test-Path -LiteralPath $previous -PathType Container)) {
            throw "Missing B150 base for ${variant}: $previous"
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

        $patchLog = Join-Path $out "b151-patch.log"
        $buildLog = Join-Path $out "b151-build.log"
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
        Write-Host "[$($mask + 1)/16] Verified $variant ($((Get-Item -LiteralPath $exe).Length) bytes)"
    }
}
finally {
    Pop-Location
}

Write-Host "Running B151 linked Holiday positive/negative validation"
& $pythonExe @pythonArgs $validator
if ($LASTEXITCODE -ne 0) {
    throw "B151 linked Holiday validation failed with exit code $LASTEXITCODE"
}

Write-Host "B151 16-state executable matrix and linked validation completed successfully."
