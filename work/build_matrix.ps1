# Reusable, data-driven replacement for the old pattern of hand-copying a
# whole build_bNNN_matrix.ps1 script per release (see work/build_b162_matrix.ps1
# for the last such script). One engine plus two small JSON files:
#   -MatrixConfig   the stable 19-variant toggle matrix (data/vf2/build-matrix-toggles.json)
#   -ReleaseConfig  this release's exe name/output prefix/optional seed paths
#
# Recreated from scratch: a prior build (tagged "Redesigned" on GitHub) used a
# script with this same name and describes these same properties in its
# release notes, but that script itself was never committed to the repo and
# was not recoverable from any local checkout when this one was written. This
# is a fresh implementation against that description, not a byte-for-byte
# restoration -- see docs/B164-release-notes.md for what was actually
# validated about it.
param(
    [Parameter(Mandatory = $true)]
    [string]$Python,
    [Parameter(Mandatory = $true)]
    [string]$MatrixConfig,
    [Parameter(Mandatory = $true)]
    [string]$ReleaseConfig
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputs = Join-Path $root "outputs"
$patcher = Join-Path $root "work\patch_mobile_furniture_pack.py"
$builder = Join-Path $root "work\build_b119.bat"
$vanillaRuntime = Join-Path $root "work\vanilla_runtime_payload"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python runtime not found: $Python"
}

# coff_patch decodes a code section before growing it, so the relative branches
# spanning the insertion point can be re-encoded. Checking here fails the whole
# matrix in a second instead of on the first variant's generation step.
& $Python -c "import capstone, PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Build dependencies are missing for $Python (capstone and/or Pillow). Run: $Python -m pip install -r requirements-build.txt"
}
if (-not (Test-Path -LiteralPath $vanillaRuntime -PathType Container)) {
    throw "work\vanilla_runtime_payload not found -- populate it with a verified vanilla VF2 install before building."
}

$matrix = Get-Content -LiteralPath $MatrixConfig -Raw | ConvertFrom-Json
$release = Get-Content -LiteralPath $ReleaseConfig -Raw | ConvertFrom-Json
$outputPrefix = $release.output_prefix
$exeName = $release.exe_name
$logRoot = Join-Path $outputs "$outputPrefix-logs"

$environmentNames = @(
    "VF2_PATCH_OUT", "VF2_BUILD_OUT", "VF2_OUTPUT_EXE", "VF2_PREVIOUS_BUILD_DIR",
    "VF2_VANILLA_RUNTIME_DIR", "VF2_ENABLE_CHEAT_UPGRADES", "VF2_ENABLE_MOBILE_RENOVATIONS",
    "VF2_ENABLE_AI_GENERATED_BATHROOM2", "VF2_ENABLE_MOBILE_SOUND_ASSETS", "VF2_ENABLE_ISLAND_EVENTS",
    "VF2_ENABLE_HOLIDAY_ORNAMENTS", "VF2_ENABLE_BEHAVIOR_PATCHES", "VF2_ENABLE_DEBUGGER_FEATURES",
    "VF2_ENABLE_HOLIDAY_BODY_TYPES", "VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK"
)

function Flag([bool]$value) { if ($value) { "1" } else { "0" } }

$results = @()
Push-Location $root
try {
    New-Item -ItemType Directory -Path $logRoot | Out-Null
    foreach ($config in $matrix.variants) {
        $out = Join-Path $outputs "$outputPrefix-$($config.name)"
        if (Test-Path -LiteralPath $out) {
            throw "Refusing to reuse matrix output: $out"
        }
        New-Item -ItemType Directory -Path $out | Out-Null

        $seedPath = $null
        if ($release.seeds.PSObject.Properties.Name -contains $config.name) {
            $seedPath = $release.seeds.$($config.name)
        }

        $env:VF2_PATCH_OUT = $out
        $env:VF2_BUILD_OUT = $out
        $env:VF2_OUTPUT_EXE = $exeName
        if ($seedPath) {
            $env:VF2_PREVIOUS_BUILD_DIR = $seedPath
        } else {
            Remove-Item -LiteralPath "Env:VF2_PREVIOUS_BUILD_DIR" -ErrorAction SilentlyContinue
        }
        $env:VF2_VANILLA_RUNTIME_DIR = $vanillaRuntime
        $env:VF2_ENABLE_CHEAT_UPGRADES = Flag $config.cheat_upgrades
        $env:VF2_ENABLE_MOBILE_RENOVATIONS = Flag $config.mobile_renovations
        $env:VF2_ENABLE_AI_GENERATED_BATHROOM2 = Flag $config.ai_generated_bathroom2
        $env:VF2_ENABLE_MOBILE_SOUND_ASSETS = "0"
        $env:VF2_ENABLE_ISLAND_EVENTS = Flag $config.island_events
        $env:VF2_ENABLE_HOLIDAY_ORNAMENTS = Flag $config.holiday_ornaments
        $env:VF2_ENABLE_BEHAVIOR_PATCHES = Flag $config.behavior_patches
        $env:VF2_ENABLE_DEBUGGER_FEATURES = "0"
        $env:VF2_ENABLE_HOLIDAY_BODY_TYPES = "1"
        $env:VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK = "0"

        $generatorStdout = Join-Path $logRoot "$($config.name).generator.stdout.log"
        $generatorStderr = Join-Path $logRoot "$($config.name).generator.stderr.log"
        $generatorCommand = '"{0}" "{1}" 1>"{2}" 2>"{3}"' -f $Python, $patcher, $generatorStdout, $generatorStderr
        & cmd.exe /d /s /c $generatorCommand
        if ($LASTEXITCODE -ne 0) { throw "Generator failed for $($config.name): $LASTEXITCODE" }

        $manifestPath = Join-Path $out "patch-manifest.json"
        $manifestObj = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

        # Fail closed on silent seed-state drift: if this variant was
        # configured with (or without) a seed, the generator's own record of
        # what it actually did must agree. A boolean-only check isn't enough:
        # find_previous_build_source() falls back to scanning outputs\ for
        # an unrelated older build if the configured path is missing/wrong-
        # shaped, and that fallback also reports status "seeded from
        # previous build" -- so also compare *which* seed was actually used
        # against the one configured for this variant, not just whether one
        # was used at all. The manifest redacts the local machine's absolute
        # path prefix (writes "<local-source>/..." instead), so compare the
        # trailing folder name rather than the full path.
        $seedStatus = $manifestObj.previous_build_seed.status
        $seedConfigured = [bool]$seedPath
        $seedUsed = ($seedStatus -eq "seeded from previous build")
        if ($seedConfigured -ne $seedUsed) {
            throw "Seed-state drift for $($config.name): configured=$seedConfigured, manifest reports status='$seedStatus'"
        }
        if ($seedConfigured) {
            $expectedSeedName = ($seedPath.TrimEnd('/', '\') -split '[/\\]')[-1]
            $actualSeedSource = [string]$manifestObj.previous_build_seed.source
            $actualSeedName = ($actualSeedSource.TrimEnd('/', '\') -split '[/\\]')[-1]
            if ($expectedSeedName -ne $actualSeedName) {
                throw "Seed identity drift for $($config.name): configured '$seedPath' (name '$expectedSeedName') but manifest recorded source '$actualSeedSource' (name '$actualSeedName')"
            }
        }

        if ($manifestObj.ScrollingStoreScene.price_multiplier.enabled -ne $config.cheat_upgrades) { throw "Cheat gate mismatch for $($config.name)" }
        if ($manifestObj.mobile_renovation_renderer.enabled -ne $config.mobile_renovations) { throw "Mobile renovation gate mismatch for $($config.name)" }
        if ($manifestObj.ai_generated_bathroom2_renovations.enabled -ne $config.ai_generated_bathroom2) { throw "Bathroom 2 gate mismatch for $($config.name)" }
        if ($config.mobile_renovations -and $manifestObj.HouseRenovations.new_count -ne 30) { throw "Native/mobile House Renovations count mismatch for $($config.name)" }
        if ($config.mobile_renovations -and $manifestObj.HouseRenovations.curtain_state_behavior.mode -ne "restart_only") { throw "Curtain restart contract missing for $($config.name)" }
        # Deliberate tripwire: bump this only when rows are added on purpose.
        # 45 CHEAT_UPGRADE_ITEMS rows + the 4 mobile Special Upgrades.
        # B173 added 7: the five wellbeing rows (0x153-0x157) and the two
        # Flea Market ownership toggles (0x158-0x159).
        # B178 added 2: the Details-screen rows Set Age to 18 (0x15A) and Add
        # Running Like (0x15B). They carry item records like every other row,
        # so they count here even though they are kept off the store's
        # services list and appear only on a villager's Details screen.
        $expectedSpecialRows = if ($config.cheat_upgrades) { 49 } else { 4 }
        if (@($manifestObj.VisibleSpecialUpgrades.added_items).Count -ne $expectedSpecialRows) { throw "Special Upgrades row count mismatch for $($config.name)" }
        $mobileSpecialRows = @($manifestObj.VisibleSpecialUpgrades.added_items | Where-Object { $_.item_id -in @("0x117", "0x118", "0x119", "0x11a") })
        if ($mobileSpecialRows.Count -ne 4) { throw "Mobile Special Upgrades rows missing for $($config.name)" }

        Get-ChildItem -LiteralPath $out -Filter "*.exe" -File | Remove-Item -Force
        $linkStdout = Join-Path $logRoot "$($config.name).link.stdout.log"
        $linkStderr = Join-Path $logRoot "$($config.name).link.stderr.log"
        $linkCommand = '"{0}" 1>"{1}" 2>"{2}"' -f $builder, $linkStdout, $linkStderr
        & cmd.exe /d /s /c $linkCommand
        if ($LASTEXITCODE -ne 0) { throw "Link failed for $($config.name): $LASTEXITCODE" }

        $exe = Join-Path $out $exeName
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Linked executable missing for $($config.name): $exe" }
        $results += [pscustomobject]@{
            name = $config.name; output = $out; seed = $seedPath
            cheat_upgrades = $config.cheat_upgrades; mobile_renovations = $config.mobile_renovations
            ai_generated_bathroom2 = $config.ai_generated_bathroom2; island_events = $config.island_events
            holiday_ornaments = $config.holiday_ornaments; behavior_patches = $config.behavior_patches
            bytes = (Get-Item -LiteralPath $exe).Length
            sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
        }
        Write-Host "[$($config.name)] linked OK: $($results[-1].sha256)"
    }
}
finally {
    foreach ($name in $environmentNames) { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue }
    Pop-Location
}

$distinctHashes = ($results | Select-Object -ExpandProperty sha256 -Unique).Count
if ($distinctHashes -ne $results.Count) {
    Write-Warning "Expected $($results.Count) byte-distinct executables, got $distinctHashes unique hashes."
}

$summary = Join-Path $outputs "$outputPrefix-summary.json"
$results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $summary -Encoding UTF8
$results | Format-Table -AutoSize
