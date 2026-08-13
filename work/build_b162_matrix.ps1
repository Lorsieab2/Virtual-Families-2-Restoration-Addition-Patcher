param(
    [Parameter(Mandatory = $true)]
    [string]$Python,
    [string]$OutputPrefix = "VF2-B162-matrix-20260812"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputs = Join-Path $root "outputs"
$patcher = Join-Path $root "work\patch_mobile_furniture_pack.py"
$builder = Join-Path $root "work\build_b119.bat"
$vanillaRuntime = Join-Path $root "work\vanilla_runtime_payload"
$exeName = "Virtual Families 2 - B162.exe"
$logRoot = Join-Path $outputs "$OutputPrefix-logs"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python runtime not found: $Python"
}

$configs = @(
    @{ Name = "core"; Seed = "VF2-B161-Native-Matrix-20260812-core-r5"; Cheat = "0"; Mobile = "0"; B2 = "0"; Island = "0"; Holiday = "0"; Behavior = "0" },
    @{ Name = "behavior_patches"; Seed = "VF2-B161-Native-Matrix-20260812-behavior_patches-r5"; Cheat = "0"; Mobile = "0"; B2 = "0"; Island = "0"; Holiday = "0"; Behavior = "1" },
    @{ Name = "cheat_upgrades"; Seed = "VF2-B161-Native-Matrix-20260812-cheat_upgrades-r5"; Cheat = "1"; Mobile = "0"; B2 = "0"; Island = "0"; Holiday = "0"; Behavior = "0" },
    @{ Name = "cheat_upgrades_behavior_patches"; Seed = "VF2-B161-Native-Matrix-20260812-cheat_upgrades_behavior_patches-r5"; Cheat = "1"; Mobile = "0"; B2 = "0"; Island = "0"; Holiday = "0"; Behavior = "1" },
    @{ Name = "cheat_upgrades_holiday_ornaments"; Seed = "VF2-B161-Native-Matrix-20260812-cheat_upgrades_holiday_ornaments-r5"; Cheat = "1"; Mobile = "0"; B2 = "0"; Island = "0"; Holiday = "1"; Behavior = "0" },
    @{ Name = "cheat_upgrades_holiday_ornaments_behavior_patches"; Seed = "VF2-B161-Native-Matrix-20260812-cheat_upgrades_holiday_ornaments_behavior_patches-r5"; Cheat = "1"; Mobile = "0"; B2 = "0"; Island = "0"; Holiday = "1"; Behavior = "1" },
    @{ Name = "holiday_ornaments"; Seed = "VF2-B161-Native-Matrix-20260812-holiday_ornaments-r5"; Cheat = "0"; Mobile = "0"; B2 = "0"; Island = "0"; Holiday = "1"; Behavior = "0" },
    @{ Name = "holiday_ornaments_behavior_patches"; Seed = "VF2-B161-Native-Matrix-20260812-holiday_ornaments_behavior_patches-r5"; Cheat = "0"; Mobile = "0"; B2 = "0"; Island = "0"; Holiday = "1"; Behavior = "1" },
    @{ Name = "island_events"; Seed = "VF2-B161-Native-Matrix-20260812-island_events"; Cheat = "0"; Mobile = "0"; B2 = "0"; Island = "1"; Holiday = "0"; Behavior = "0" },
    @{ Name = "island_events_behavior_patches"; Seed = "VF2-B161-Native-Matrix-20260812-island_events_behavior_patches-r5"; Cheat = "0"; Mobile = "0"; B2 = "0"; Island = "1"; Holiday = "0"; Behavior = "1" },
    @{ Name = "island_events_cheat_upgrades"; Seed = "VF2-B161-Native-Matrix-20260812-island_events_cheat_upgrades-r5"; Cheat = "1"; Mobile = "0"; B2 = "0"; Island = "1"; Holiday = "0"; Behavior = "0" },
    @{ Name = "island_events_cheat_upgrades_behavior_patches"; Seed = "VF2-B161-Native-Matrix-20260812-island_events_cheat_upgrades_behavior_patches-r5"; Cheat = "1"; Mobile = "0"; B2 = "0"; Island = "1"; Holiday = "0"; Behavior = "1" },
    @{ Name = "island_events_cheat_upgrades_holiday_ornaments"; Seed = "VF2-B161-Native-Matrix-20260812-island_events_cheat_upgrades_holiday_ornaments-r5"; Cheat = "1"; Mobile = "0"; B2 = "0"; Island = "1"; Holiday = "1"; Behavior = "0" },
    @{ Name = "island_events_cheat_upgrades_holiday_ornaments_behavior_patches"; Seed = "VF2-B161-Native-Matrix-20260812-island_events_cheat_upgrades_holiday_ornaments_behavior_patches-r5"; Cheat = "1"; Mobile = "0"; B2 = "0"; Island = "1"; Holiday = "1"; Behavior = "1" },
    @{ Name = "island_events_holiday_ornaments"; Seed = "VF2-B161-Native-Matrix-20260812-island_events_holiday_ornaments-r5"; Cheat = "0"; Mobile = "0"; B2 = "0"; Island = "1"; Holiday = "1"; Behavior = "0" },
    @{ Name = "island_events_holiday_ornaments_behavior_patches"; Seed = "VF2-B161-Native-Matrix-20260812-island_events_holiday_ornaments_behavior_patches-r5"; Cheat = "0"; Mobile = "0"; B2 = "0"; Island = "1"; Holiday = "1"; Behavior = "1" },
    @{ Name = "mobile_renovations"; Seed = "VF2-B161-Mobile-Renovations-20260812"; Cheat = "0"; Mobile = "1"; B2 = "1"; Island = "0"; Holiday = "0"; Behavior = "0" },
    @{ Name = "cheat_upgrades_mobile_renovations"; Seed = "VF2-B161-Cheat-Mobile-Renovations-20260812"; Cheat = "1"; Mobile = "1"; B2 = "1"; Island = "0"; Holiday = "0"; Behavior = "0" },
    @{ Name = "final_all_enabled"; Seed = "VF2-B161-Final-All-Enabled-20260812"; Cheat = "1"; Mobile = "1"; B2 = "1"; Island = "1"; Holiday = "1"; Behavior = "1" }
)

$environmentNames = @(
    "VF2_PATCH_OUT", "VF2_BUILD_OUT", "VF2_OUTPUT_EXE", "VF2_PREVIOUS_BUILD_DIR",
    "VF2_VANILLA_RUNTIME_DIR", "VF2_ENABLE_CHEAT_UPGRADES", "VF2_ENABLE_MOBILE_RENOVATIONS",
    "VF2_ENABLE_AI_GENERATED_BATHROOM2", "VF2_ENABLE_MOBILE_SOUND_ASSETS", "VF2_ENABLE_ISLAND_EVENTS",
    "VF2_ENABLE_HOLIDAY_ORNAMENTS", "VF2_ENABLE_BEHAVIOR_PATCHES", "VF2_ENABLE_DEBUGGER_FEATURES",
    "VF2_ENABLE_HOLIDAY_BODY_TYPES", "VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK"
)

$results = @()
Push-Location $root
try {
    New-Item -ItemType Directory -Path $logRoot | Out-Null
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
        $env:VF2_ENABLE_MOBILE_RENOVATIONS = $config.Mobile
        $env:VF2_ENABLE_AI_GENERATED_BATHROOM2 = $config.B2
        $env:VF2_ENABLE_MOBILE_SOUND_ASSETS = "0"
        $env:VF2_ENABLE_ISLAND_EVENTS = $config.Island
        $env:VF2_ENABLE_HOLIDAY_ORNAMENTS = $config.Holiday
        $env:VF2_ENABLE_BEHAVIOR_PATCHES = $config.Behavior
        $env:VF2_ENABLE_DEBUGGER_FEATURES = "0"
        $env:VF2_ENABLE_HOLIDAY_BODY_TYPES = "1"
        $env:VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK = "0"

        $generatorStdout = Join-Path $logRoot "$($config.Name).generator.stdout.log"
        $generatorStderr = Join-Path $logRoot "$($config.Name).generator.stderr.log"
        $generatorCommand = '"{0}" "{1}" 1>"{2}" 2>"{3}"' -f $Python, $patcher, $generatorStdout, $generatorStderr
        & cmd.exe /d /s /c $generatorCommand
        if ($LASTEXITCODE -ne 0) { throw "Generator failed for $($config.Name): $LASTEXITCODE" }

        $manifestPath = Join-Path $out "patch-manifest.json"
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.ScrollingStoreScene.price_multiplier.enabled -ne ($config.Cheat -eq "1")) { throw "Cheat gate mismatch for $($config.Name)" }
        if ($manifest.mobile_renovation_renderer.enabled -ne ($config.Mobile -eq "1")) { throw "Mobile renovation gate mismatch for $($config.Name)" }
        if ($manifest.ai_generated_bathroom2_renovations.enabled -ne ($config.B2 -eq "1")) { throw "Bathroom 2 gate mismatch for $($config.Name)" }
        if ($config.Mobile -eq "1" -and $manifest.HouseRenovations.new_count -ne 30) { throw "Native/mobile House Renovations count mismatch for $($config.Name)" }
        if ($config.Mobile -eq "1" -and $manifest.HouseRenovations.curtain_state_behavior.mode -ne "restart_only") { throw "Curtain restart contract missing for $($config.Name)" }
        $expectedSpecialRows = if ($config.Cheat -eq "1") { 40 } else { 4 }
        if (@($manifest.VisibleSpecialUpgrades.added_items).Count -ne $expectedSpecialRows) { throw "Special Upgrades row count mismatch for $($config.Name)" }
        $mobileSpecialRows = @($manifest.VisibleSpecialUpgrades.added_items | Where-Object { $_.item_id -in @("0x117", "0x118", "0x119", "0x11a") })
        if ($mobileSpecialRows.Count -ne 4) { throw "Mobile Special Upgrades rows missing for $($config.Name)" }

        Get-ChildItem -LiteralPath $out -Filter "*.exe" -File | Remove-Item -Force
        $linkStdout = Join-Path $logRoot "$($config.Name).link.stdout.log"
        $linkStderr = Join-Path $logRoot "$($config.Name).link.stderr.log"
        $linkCommand = '"{0}" 1>"{1}" 2>"{2}"' -f $builder, $linkStdout, $linkStderr
        & cmd.exe /d /s /c $linkCommand
        if ($LASTEXITCODE -ne 0) { throw "Link failed for $($config.Name): $LASTEXITCODE" }

        $exe = Join-Path $out $exeName
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Linked executable missing for $($config.Name): $exe" }
        $results += [pscustomobject]@{
            name = $config.Name; output = $out; seed = $seed
            cheat_upgrades = ($config.Cheat -eq "1"); mobile_renovations = ($config.Mobile -eq "1")
            bathroom2 = ($config.B2 -eq "1"); bytes = (Get-Item -LiteralPath $exe).Length
            sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
        }
    }
}
finally {
    foreach ($name in $environmentNames) { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue }
    Pop-Location
}

$summary = Join-Path $outputs "$OutputPrefix-summary.json"
$results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $summary -Encoding UTF8
$results | Format-Table -AutoSize
