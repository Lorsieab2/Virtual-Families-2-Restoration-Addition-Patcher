param(
    [Parameter(Mandatory = $true)]
    [string]$Python,
    [string]$OutputPrefix = "VF2-B158-toggle-matrix-65155b4"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputs = Join-Path $root "outputs"
$patcher = Join-Path $root "work\patch_mobile_furniture_pack.py"
$builder = Join-Path $root "work\build_b119.bat"
$vanillaRuntime = Join-Path $root "work\vanilla_runtime_payload"
$exeName = "Virtual Families 2 - Toggle Matrix.exe"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python runtime not found: $Python"
}

$configs = @(
    @{
        Name = "core"
        Cheat = "0"
        Renovations = "0"
        Seed = "VF2-Mobile-Furniture-Tree-Autonomy-B158-core-overlay-validation"
    },
    @{
        Name = "cheat"
        Cheat = "1"
        Renovations = "0"
        Seed = "VF2-Mobile-Furniture-Tree-Autonomy-B158-cheat-overlay-validation"
    },
    @{
        Name = "renovations"
        Cheat = "0"
        Renovations = "1"
        Seed = "VF2-Mobile-Furniture-Tree-Autonomy-B158-renovations-overlay-validation"
    },
    @{
        Name = "cheat-renovations"
        Cheat = "1"
        Renovations = "1"
        Seed = "VF2-Mobile-Furniture-Tree-Autonomy-B158-state-machine-removal-validation2"
    }
)

$environmentNames = @(
    "VF2_PATCH_OUT",
    "VF2_BUILD_OUT",
    "VF2_OUTPUT_EXE",
    "VF2_PREVIOUS_BUILD_DIR",
    "VF2_VANILLA_RUNTIME_DIR",
    "VF2_ENABLE_CHEAT_UPGRADES",
    "VF2_ENABLE_MOBILE_RENOVATIONS",
    "VF2_ENABLE_MOBILE_SOUND_ASSETS",
    "VF2_ENABLE_ISLAND_EVENTS",
    "VF2_ENABLE_HOLIDAY_ORNAMENTS",
    "VF2_ENABLE_BEHAVIOR_PATCHES",
    "VF2_ENABLE_DEBUGGER_FEATURES",
    "VF2_ENABLE_HOLIDAY_BODY_TYPES",
    "VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK"
)

$results = @()
Push-Location $root
try {
    foreach ($config in $configs) {
        $seed = Join-Path $outputs $config.Seed
        $out = Join-Path $outputs "$OutputPrefix-$($config.Name)"
        if (-not (Test-Path -LiteralPath $seed -PathType Container)) {
            throw "Matrix seed not found: $seed"
        }
        if (Test-Path -LiteralPath $out) {
            throw "Refusing to reuse matrix output: $out"
        }
        New-Item -ItemType Directory -Path $out | Out-Null

        $env:VF2_PATCH_OUT = $out
        $env:VF2_BUILD_OUT = $out
        $env:VF2_OUTPUT_EXE = $exeName
        $env:VF2_PREVIOUS_BUILD_DIR = $seed
        $env:VF2_VANILLA_RUNTIME_DIR = $vanillaRuntime
        $env:VF2_ENABLE_CHEAT_UPGRADES = $config.Cheat
        $env:VF2_ENABLE_MOBILE_RENOVATIONS = $config.Renovations
        $env:VF2_ENABLE_MOBILE_SOUND_ASSETS = "0"
        $env:VF2_ENABLE_ISLAND_EVENTS = "0"
        $env:VF2_ENABLE_HOLIDAY_ORNAMENTS = "0"
        $env:VF2_ENABLE_BEHAVIOR_PATCHES = "0"
        $env:VF2_ENABLE_DEBUGGER_FEATURES = "0"
        $env:VF2_ENABLE_HOLIDAY_BODY_TYPES = "1"
        $env:VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK = "0"

        $generatorStdout = Join-Path $out "generator.stdout.log"
        $generatorStderr = Join-Path $out "generator.stderr.log"
        $generatorCommand = '"{0}" "{1}" 1>"{2}" 2>"{3}"' -f `
            $Python, $patcher, $generatorStdout, $generatorStderr
        & cmd.exe /d /s /c $generatorCommand
        if ($LASTEXITCODE -ne 0) {
            throw "Generator failed for $($config.Name): $LASTEXITCODE"
        }

        $manifestPath = Join-Path $out "patch-manifest.json"
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        $expectedCheat = $config.Cheat -eq "1"
        $expectedRenovations = $config.Renovations -eq "1"
        if ($manifest.ScrollingStoreScene.price_multiplier.enabled -ne $expectedCheat) {
            throw "Cheat gate mismatch for $($config.Name)"
        }
        if ($manifest.mobile_renovation_renderer.enabled -ne $expectedRenovations) {
            throw "Renovation gate mismatch for $($config.Name)"
        }
        if ($manifest.MobileSoundAssets.enabled -ne $false -or
            $manifest.MobileSoundAssets.default_off -ne $true -or
            $manifest.MobileSoundAssets.status -ne "stock_wav_routes_preserved") {
            throw "Mobile sound off-state mismatch for $($config.Name)"
        }
        if ($manifest.BehaviorPatchesGate.enabled -ne $false -or
            $manifest.HolidayOrnamentsCollection.enabled -ne $false -or
            $manifest.IncreaseChildLimitContract.enabled -ne $false -or
            @($manifest.IslandEvents.added).Count -ne 0) {
            throw "Hiatus or optional compile gate mismatch for $($config.Name)"
        }

        # Seed trees contain old executables. Remove only those copied files
        # after generation and before linking this exact matrix state.
        Get-ChildItem -LiteralPath $out -Filter "*.exe" -File | Remove-Item -Force

        $linkStdout = Join-Path $out "link.stdout.log"
        $linkStderr = Join-Path $out "link.stderr.log"
        $linkCommand = '"{0}" 1>"{1}" 2>"{2}"' -f `
            $builder, $linkStdout, $linkStderr
        & cmd.exe /d /s /c $linkCommand
        if ($LASTEXITCODE -ne 0) {
            throw "Link failed for $($config.Name): $LASTEXITCODE"
        }

        $exe = Join-Path $out $exeName
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
            throw "Linked executable missing for $($config.Name): $exe"
        }
        $results += [pscustomobject]@{
            name = $config.Name
            output = $out
            seed = $seed
            cheat_upgrades = $expectedCheat
            mobile_renovations = $expectedRenovations
            mobile_sound_assets = $false
            bytes = (Get-Item -LiteralPath $exe).Length
            sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
        }
    }
}
finally {
    foreach ($name in $environmentNames) {
        Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
    }
    Pop-Location
}

$summary = Join-Path $outputs "$OutputPrefix-summary.json"
$results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $summary -Encoding UTF8
$results | Format-Table -AutoSize
