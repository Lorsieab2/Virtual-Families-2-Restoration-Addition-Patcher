# Fast, single-configuration playtest build. Wraps the exact recipe used by
# build_matrix.ps1's per-variant loop (generator -> build_b119.bat link) but
# for ONE build instead of the full 19-variant matrix, with upfront checks for
# the local, gitignored support directories a fresh checkout/worktree won't
# have (these are what actually ate the time on 2026-08-16: the matrix/link
# scripts assume they're already there and fail deep into a cryptic LNK1181
# instead of saying what's missing).
#
# Added after that exact bug: VF2MarriagePair's fallback silently paired up
# any two qualifying resident adults as "the married couple", which blocked
# Force Marriage Email for players with no spouse at all. The logic bug
# itself has nothing to do with the build system, but confirming the fix and
# getting a testable exe into the user's hands took far longer than it should
# have -- this script exists so "give me a build with the fix" is one
# command, not a from-scratch rediscovery of build_matrix.ps1 + build_b119.bat
# + four missing junctions.
#
# Usage:
#   pwsh work\build_playtest.ps1
#   pwsh work\build_playtest.ps1 -OutName "MyTestBuild" -Cheat:$false
#
# Defaults to every optional patch enabled (matches the "final_all_enabled"
# matrix variant), since that's what playtest requests almost always want.
param(
    [string]$OutName,
    [string]$ExeName = "Virtual Families 2 - Playtest Build.exe",
    [bool]$Cheat = $true,
    [bool]$MobileRenovations = $true,
    [bool]$AIBathroom2 = $true,
    [bool]$IslandEvents = $true,
    [bool]$HolidayOrnaments = $true,
    [bool]$BehaviorPatches = $true,
    [bool]$MobileFurnitureBehaviors = $true,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

# ---- Preflight: fail fast with a clear message instead of a deep LNK error.
# Every one of these is gitignored local build support data (see
# .gitignore's /work/** rule) that a fresh clone or `git worktree add` will
# not have. Junction them in from an existing checkout that has them rather
# than copying -- they're large and read-only for this purpose.
$requiredDirs = @(
    "work\vanilla_runtime_payload",
    "work\generated_import_libs",
    "work\desktop_obj_files",
    "work\desktop_runtime_dlls"
)
$missing = $requiredDirs | Where-Object { -not (Test-Path (Join-Path $root $_)) }
if ($missing) {
    Write-Host "Missing local build support directories (gitignored, not part of git):" -ForegroundColor Yellow
    $missing | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "If another checkout of this repo already has them, junction each in, e.g.:" -ForegroundColor Yellow
    Write-Host '  New-Item -ItemType Junction -Path "<this-repo>\work\vanilla_runtime_payload" -Target "<other-checkout>\work\vanilla_runtime_payload"' -ForegroundColor Yellow
    throw "Cannot build: missing support directories listed above."
}

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python runtime not found: $Python"
}

$vswhere = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
$vcvarsall = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
if (-not (Test-Path -LiteralPath $vcvarsall)) {
    throw "MSVC vcvarsall.bat not found at expected path: $vcvarsall (build_b119.bat hardcodes this -- update both if VS moves)."
}

# ---- Output location.
if (-not $OutName) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutName = "VF2-Playtest-$stamp"
}
$out = Join-Path $root "outputs\$OutName"
if (Test-Path -LiteralPath $out) {
    throw "Refusing to reuse existing output directory: $out"
}
New-Item -ItemType Directory -Path $out | Out-Null
# Logs live in a sibling directory, not inside $out: the generator's own
# packaging step (remove_package_development_artifacts) recursively deletes
# dev-artifact-shaped files from $out, including a log written there mid-run.
$logDir = Join-Path $root "outputs\$OutName-logs"
New-Item -ItemType Directory -Path $logDir | Out-Null

function Flag([bool]$value) { if ($value) { "1" } else { "0" } }

$env:VF2_PATCH_OUT = $out
$env:VF2_BUILD_OUT = $out
$env:VF2_OUTPUT_EXE = $ExeName
Remove-Item Env:VF2_PREVIOUS_BUILD_DIR -ErrorAction SilentlyContinue
$env:VF2_VANILLA_RUNTIME_DIR = Join-Path $root "work\vanilla_runtime_payload"
$env:VF2_ENABLE_CHEAT_UPGRADES = Flag $Cheat
$env:VF2_ENABLE_MOBILE_RENOVATIONS = Flag $MobileRenovations
$env:VF2_ENABLE_AI_GENERATED_BATHROOM2 = Flag $AIBathroom2
$env:VF2_ENABLE_MOBILE_SOUND_ASSETS = "0"
$env:VF2_ENABLE_ISLAND_EVENTS = Flag $IslandEvents
$env:VF2_ENABLE_HOLIDAY_ORNAMENTS = Flag $HolidayOrnaments
$env:VF2_ENABLE_BEHAVIOR_PATCHES = Flag $BehaviorPatches
$env:VF2_ENABLE_DEBUGGER_FEATURES = "0"
$env:VF2_ENABLE_HOLIDAY_BODY_TYPES = "1"
$env:VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK = "0"

$environmentNames = @(
    "VF2_PATCH_OUT", "VF2_BUILD_OUT", "VF2_OUTPUT_EXE", "VF2_PREVIOUS_BUILD_DIR",
    "VF2_VANILLA_RUNTIME_DIR", "VF2_ENABLE_CHEAT_UPGRADES", "VF2_ENABLE_MOBILE_RENOVATIONS",
    "VF2_ENABLE_AI_GENERATED_BATHROOM2", "VF2_ENABLE_MOBILE_SOUND_ASSETS", "VF2_ENABLE_ISLAND_EVENTS",
    "VF2_ENABLE_HOLIDAY_ORNAMENTS", "VF2_ENABLE_BEHAVIOR_PATCHES", "VF2_ENABLE_DEBUGGER_FEATURES",
    "VF2_ENABLE_HOLIDAY_BODY_TYPES", "VF2_ALLOW_LEGACY_OUTPUT_RUNTIME_FALLBACK"
)

try {
    Write-Host "[1/2] Generating patched sources/objects -> $out" -ForegroundColor Cyan
    $genLog = Join-Path $logDir "generator.log"
    & cmd.exe /d /s /c ('"{0}" "work\patch_mobile_furniture_pack.py" > "{1}" 2>&1' -f $Python, $genLog)
    if ($LASTEXITCODE -ne 0) {
        Get-Content -LiteralPath $genLog -Tail 40
        throw "Generator failed (exit $LASTEXITCODE). Last 40 lines of $genLog printed above."
    }
    if (-not (Test-Path (Join-Path $out "patch-manifest.json"))) {
        throw "Generator reported success but patch-manifest.json is missing from $out."
    }
    if ($MobileFurnitureBehaviors) {
        # Restore only the four previously validated chaise behavior maps.
        # The generator's base payload intentionally contains rendered-only
        # maps, which makes LinkPeepToFurniture reject a manual lounger drop.
        $chaiseMapSource = Join-Path $root "patcher_assets\optional_patches\mobile_furniture_behaviors\pc_fmaps"
        $assetDestination = Join-Path $out "Assets"
        $chaiseMapNames = @(
            "Chaise_blue.png.fmap",
            "Chaise_brown.png.fmap",
            "Chaise_green.png.fmap",
            "Chaise_red.png.fmap"
        )
        foreach ($name in $chaiseMapNames) {
            $sourceMap = Join-Path $chaiseMapSource $name
            $targetMap = Join-Path $assetDestination $name
            if (-not (Test-Path -LiteralPath $sourceMap -PathType Leaf)) {
                throw "Validated chaise behavior map is missing: $sourceMap"
            }
            Copy-Item -LiteralPath $sourceMap -Destination $targetMap -Force
            if ((Get-FileHash -LiteralPath $sourceMap -Algorithm SHA256).Hash -ne
                (Get-FileHash -LiteralPath $targetMap -Algorithm SHA256).Hash) {
                throw "Chaise behavior map copy drifted: $name"
            }
        }
    }

    Write-Host "[2/2] Compiling and linking (this calls vcvarsall.bat x86 + cl + link)..." -ForegroundColor Cyan
    Get-ChildItem -LiteralPath $out -Filter "*.exe" -File -ErrorAction SilentlyContinue | Remove-Item -Force
    $linkLog = Join-Path $logDir "link.log"
    & cmd.exe /d /s /c ('"work\build_b119.bat" > "{0}" 2>&1' -f $linkLog)
    if ($LASTEXITCODE -ne 0) {
        Get-Content -LiteralPath $linkLog -Tail 40
        throw "Compile/link failed (exit $LASTEXITCODE). Last 40 lines of $linkLog printed above."
    }
    if ($MobileFurnitureBehaviors) {
        $linkedExe = Join-Path $out $ExeName
        & $Python "work\enable_runtime_flag.py" $linkedExe ".vf2beh"
        if ($LASTEXITCODE -ne 0) {
            throw "Could not enable the mobile-furniture runtime gate in the playtest executable."
        }
    }
}
finally {
    foreach ($name in $environmentNames) { Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue }
}

$exe = Join-Path $out $ExeName
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Link reported success but the executable is missing: $exe"
}
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Write-Host ""
Write-Host "Build OK:" -ForegroundColor Green
Write-Host "  $exe"
Write-Host "  $((Get-Item $exe).Length) bytes, SHA256 $hash"
Write-Host ""
Write-Host "This is a complete standalone folder ($out) -- copy the whole" -ForegroundColor Green
Write-Host "thing to hand it off; it does not need anything from outside itself." -ForegroundColor Green
Write-Host "Logs: $logDir"
