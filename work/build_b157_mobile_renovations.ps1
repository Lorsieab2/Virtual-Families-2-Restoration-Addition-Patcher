param(
    [string]$Python = "",
    [string]$PreviousBuildDir = "",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputs = Join-Path $root "outputs"
$patcher = Join-Path $root "work\patch_mobile_furniture_pack.py"
$builder = Join-Path $root "work\build_b119.bat"
$exeName = "Virtual Families 2 - Mobile Renovations.exe"

if ([string]::IsNullOrWhiteSpace($PreviousBuildDir)) {
    $PreviousBuildDir = Join-Path $outputs "VF2-Mobile-Furniture-With-Island-Events-B156-core"
}
else {
    $PreviousBuildDir = [IO.Path]::GetFullPath($PreviousBuildDir)
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $outputs "VF2-Mobile-Furniture-With-Island-Events-B157-mobile_renovations"
}
else {
    $OutputDir = [IO.Path]::GetFullPath($OutputDir)
}

if (-not (Test-Path -LiteralPath $patcher -PathType Leaf)) {
    throw "Patcher source not found: $patcher"
}
if (-not (Test-Path -LiteralPath $builder -PathType Leaf)) {
    throw "Build script not found: $builder"
}
if (-not (Test-Path -LiteralPath $PreviousBuildDir -PathType Container)) {
    throw "Previous build directory not found: $PreviousBuildDir"
}
foreach ($requiredDir in @("Images", "Sounds")) {
    if (-not (Test-Path -LiteralPath (Join-Path $PreviousBuildDir $requiredDir) -PathType Container)) {
        throw "Previous build is missing required runtime directory: $requiredDir"
    }
}
if (Test-Path -LiteralPath $OutputDir) {
    throw "Refusing to overwrite existing output directory: $OutputDir"
}

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
        throw "Python 3 was not found. Pass -Python or set VF2_PYTHON."
    }
    $pythonExe = $pythonCommand.Source
}

$environmentNames = @(
    "VF2_PATCH_OUT",
    "VF2_BUILD_OUT",
    "VF2_OUTPUT_EXE",
    "VF2_PREVIOUS_BUILD_DIR",
    "VF2_ENABLE_MOBILE_RENOVATIONS",
    "VF2_ENABLE_ISLAND_EVENTS",
    "VF2_ENABLE_CHEAT_UPGRADES",
    "VF2_ENABLE_HOLIDAY_ORNAMENTS",
    "VF2_ENABLE_BEHAVIOR_PATCHES",
    "VF2_ENABLE_DEBUGGER_FEATURES"
)

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$patchLog = Join-Path $OutputDir "b157-mobile-renovations-patch.log"
$buildLog = Join-Path $OutputDir "b157-mobile-renovations-build.log"

Push-Location $root
try {
    $env:VF2_PATCH_OUT = $OutputDir
    $env:VF2_BUILD_OUT = $OutputDir
    $env:VF2_OUTPUT_EXE = $exeName
    $env:VF2_PREVIOUS_BUILD_DIR = $PreviousBuildDir
    $env:VF2_ENABLE_MOBILE_RENOVATIONS = "1"
    $env:VF2_ENABLE_ISLAND_EVENTS = "0"
    $env:VF2_ENABLE_CHEAT_UPGRADES = "0"
    $env:VF2_ENABLE_HOLIDAY_ORNAMENTS = "0"
    $env:VF2_ENABLE_BEHAVIOR_PATCHES = "0"
    $env:VF2_ENABLE_DEBUGGER_FEATURES = "0"

    & $pythonExe @pythonArgs $patcher *> $patchLog
    if ($LASTEXITCODE -ne 0) {
        Get-Content -LiteralPath $patchLog -Tail 80
        throw "B157 mobile-renovations patch generation failed: $LASTEXITCODE"
    }

    $manifestPath = Join-Path $OutputDir "patch-manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Patch manifest missing: $manifestPath"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.mobile_renovation_renderer.enabled -ne $true) {
        throw "Generated manifest did not enable the mobile-renovations renderer"
    }
    if ($manifest.mobile_renovation_renderer_validation.status -ne "passed") {
        throw "Generated mobile-renovations renderer contract did not pass"
    }
    if ($manifest.mobile_renovation_renderer_validation.style_catalog.status -ne "passed") {
        throw "Generated mobile-renovations style catalog contract did not pass"
    }
    $runtimeArt = Join-Path $OutputDir "Images\MobileRenovations"
    $runtimeCount = @(Get-ChildItem -LiteralPath $runtimeArt -Filter "*.png" -File).Count
    if ($runtimeCount -ne 15) {
        throw "Expected 15 runtime renovation PNGs, found $runtimeCount"
    }

    & cmd.exe /d /c $builder *> $buildLog
    if ($LASTEXITCODE -ne 0) {
        Get-Content -LiteralPath $buildLog -Tail 120
        throw "B157 mobile-renovations link failed: $LASTEXITCODE"
    }

    $exePath = Join-Path $OutputDir $exeName
    if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
        throw "Built EXE missing: $exePath"
    }
    $exe = Get-Item -LiteralPath $exePath
    [pscustomobject]@{
        status = "passed"
        output = $OutputDir
        executable = $exe.Name
        bytes = $exe.Length
        sha256 = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash
        image_count = $runtimeCount
        hook = $manifest.mobile_renovation_renderer.hook.insert_offset
        image_base = $manifest.theGraphicsManager.mobile_renovation_images.image_base
    } | Format-List
}
finally {
    foreach ($name in $environmentNames) {
        Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
    }
    Pop-Location
}
