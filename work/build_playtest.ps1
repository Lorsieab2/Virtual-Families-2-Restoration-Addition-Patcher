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
    # VF2 derives its save folder from the executable filename
    # (Documents\LDW\<exe name>), so changing this name per build strands the
    # previous playtest family in an old folder. Keep one stable name.
    [string]$ExeName = "Virtual Families 2 Modded Playtest 2.exe",
    [bool]$Cheat = $true,
    [bool]$MobileRenovations = $true,
    [bool]$AIBathroom2 = $true,
    [bool]$IslandEvents = $true,
    [bool]$HolidayOrnaments = $true,
    [bool]$BehaviorPatches = $true,
    [bool]$MobileFurnitureBehaviors = $true,
    [bool]$HolidayFurnitureGoals = $true,
    [bool]$AllowOlderPregnancies = $true,
    [bool]$OlderVillagerMortality = $true,
    [bool]$StoreScrollBar = $true,
    # A previous build to inherit runtime art from. 635 Images --
    # mobile furniture art, 448 VillagerBodies frames, 61 upgrade icons --
    # exist in neither the repository nor the vanilla payload, so they
    # reach a build only this way. Leaving it unset does not guarantee an
    # uninherited build: the generator also scans outputs\ for an older one.
    # Whichever seed it resolves is reported after generation.
    [string]$PreviousBuildDir,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

# Images that reach a build only by inheriting from a previous build output.
# They exist in neither the repository nor work/vanilla_runtime_payload, so an
# unseeded build omits every one of them and still reports success. The measured
# inventory is recorded in data/vf2/inherited-only-images.json; validating the
# whole list rather than a sample means a seed that lost any single file is
# rejected instead of silently dropping it.
$inheritedOnlyIndexPath = Join-Path (Join-Path (Join-Path $PSScriptRoot "..") "data") "vf2"
$inheritedOnlyIndexPath = Join-Path $inheritedOnlyIndexPath "inherited-only-images.json"
if (-not (Test-Path -LiteralPath $inheritedOnlyIndexPath)) {
    throw "Missing inherited-art inventory: $inheritedOnlyIndexPath"
}
$inheritedOnlyIndex = Get-Content -LiteralPath $inheritedOnlyIndexPath -Raw | ConvertFrom-Json
# Editing sources -- .xcf files and the Upgrades "invisible images" /
# "original images" working folders -- are recorded in the historical
# inventory but are not runtime art. The engine never loads them and the
# offline bundle excludes them, so a build is not required to produce them and
# validating them here would fail every build that correctly omits them.
$nonRuntimeInherited = @{}
foreach ($rel in @($inheritedOnlyIndex.non_runtime_files)) {
    if ($rel) { $nonRuntimeInherited[$rel] = $true }
}
$inheritedOnlyImages = @($inheritedOnlyIndex.files |
    Where-Object { -not $nonRuntimeInherited.ContainsKey($_) } |
    ForEach-Object { "Images/$_" })
if ($inheritedOnlyImages.Count -eq 0) {
    throw "Inherited-art inventory is empty: $inheritedOnlyIndexPath"
}

function Get-MissingInheritedArt([string]$Root) {
    $missing = @()
    foreach ($rel in $inheritedOnlyImages) {
        $path = Join-Path $Root ($rel -replace "/", [string][char]92)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { $missing += $rel }
    }
    return $missing
}

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

# A previous build supplied here has to be validated before anything is
# created: throwing after $out exists leaves an abandoned directory that the
# reuse guard below then rejects, so a corrected -PreviousBuildDir could not be
# retried with the same -OutName. Require the runtime subdirectories too --
# find_previous_build_source() silently ignores a directory without them and
# falls through to scanning outputs\\ or to building unseeded, which is the
# exact silent-miss this parameter exists to prevent.
if ($PreviousBuildDir) {
    if (-not (Test-Path -LiteralPath $PreviousBuildDir -PathType Container)) {
        throw "PreviousBuildDir does not exist: $PreviousBuildDir"
    }
    foreach ($needed in @("Images", "Sounds")) {
        if (-not (Test-Path -LiteralPath (Join-Path $PreviousBuildDir $needed) -PathType Container)) {
            throw "PreviousBuildDir is not a usable build output (missing $needed): $PreviousBuildDir"
        }
    }
    # Images + Sounds also describes workanilla_runtime_payload, which holds
    # none of the inheritance-only art this option exists to carry forward.
    # Seeding from it would satisfy the manifest checks below and still produce
    # a green build with the furniture, body and upgrade art missing. A real
    # build output is distinguishable two ways: it has a patch-manifest.json,
    # and its Images tree is larger than a clean install's.
    if (-not (Test-Path -LiteralPath (Join-Path $PreviousBuildDir "patch-manifest.json") -PathType Leaf)) {
        throw ("PreviousBuildDir has no patch-manifest.json, so it is not a build output " +
            "(a vanilla runtime payload cannot supply inheritance-only art): $PreviousBuildDir")
    }
    # An aggregate count is not enough either: an earlier *uninherited* playtest
    # output has Images, Sounds and a patch-manifest.json, and its 6672 generated
    # images comfortably exceed a clean install's 655, yet it is missing every one
    # of the inheritance-only files. Chaining from it would pass every check above
    # and still ship without the art. So require files that were measured as
    # absent from an uninherited build. Representative, not exhaustive -- enough
    # to tell a real inherited build from one that cannot pass the art on.
    #
    # A seed no longer has to be complete: restore_preserved_inherited_art()
    # supplies anything it lacks from the tracked store, and verifies it. This
    # used to abort the build, which now needlessly refuses a partial or older
    # seed the build handles perfectly well. Still reported, because a seed
    # missing art usually means the wrong directory was passed.
    $missingProbes = Get-MissingInheritedArt $PreviousBuildDir
    if ($missingProbes.Count -gt 0) {
        Write-Host ("  seed is missing {0} of {1} inheritance-only images; they will be supplied from patcher_assets/inherited_runtime_images" -f $missingProbes.Count, $inheritedOnlyImages.Count) -ForegroundColor Yellow
    } else {
        Write-Host ("  seed carries all {0} inheritance-only images" -f $inheritedOnlyImages.Count)
    }
    $PreviousBuildDir = (Resolve-Path -LiteralPath $PreviousBuildDir).Path
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
if ($PreviousBuildDir) {
    $env:VF2_PREVIOUS_BUILD_DIR = $PreviousBuildDir
    Write-Host "Inheriting runtime art from: $PreviousBuildDir" -ForegroundColor Cyan
} else {
    # Clear any inherited value so an unseeded build is deterministic rather
    # than silently picking up whatever the shell happened to export.
    Remove-Item Env:VF2_PREVIOUS_BUILD_DIR -ErrorAction SilentlyContinue
    Write-Host ("No -PreviousBuildDir. The generator may still auto-discover a previous " +
        "build under outputs" + [char]92 + "; whichever seed it resolves is reported below.") -ForegroundColor Yellow
}
$env:VF2_VANILLA_RUNTIME_DIR = Join-Path $root "work\vanilla_runtime_payload"
$env:VF2_ENABLE_CHEAT_UPGRADES = Flag $Cheat
$env:VF2_ENABLE_MOBILE_RENOVATIONS = Flag $MobileRenovations
$env:VF2_ENABLE_AI_GENERATED_BATHROOM2 = Flag $AIBathroom2
$env:VF2_ENABLE_MOBILE_SOUND_ASSETS = "1"
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

    # Fail closed on silent seed drift. find_previous_build_source() falls back
    # to scanning outputs\\ for an unrelated older build, and that fallback also
    # reports status "seeded from previous build" -- so compare which seed was
    # actually used, not just whether one was. The manifest redacts the local
    # absolute path prefix, so compare the trailing folder name (same approach
    # as build_matrix.ps1).
    $manifestObj = Get-Content -LiteralPath (Join-Path $out "patch-manifest.json") -Raw | ConvertFrom-Json
    $seedUsed = ($manifestObj.previous_build_seed.status -eq "seeded from previous build")
    if ($PreviousBuildDir -and -not $seedUsed) {
        throw ("Seed-state drift: -PreviousBuildDir was supplied but the manifest reports status '{0}'." -f `
            $manifestObj.previous_build_seed.status)
    }
    if (-not $PreviousBuildDir -and $seedUsed) {
        # Not a failure: previous_build_source_dirs() also scans outputs\ for an
        # older build, and clearing the environment variable does not switch that
        # off. Throwing here would break the documented default invocation in any
        # established build checkout, so report the seed the generator actually
        # resolved instead of pretending the build was uninherited.
        Write-Host ("  NOTE: no -PreviousBuildDir was given, but the generator auto-discovered a seed: " +
            [string]$manifestObj.previous_build_seed.source) -ForegroundColor Yellow
    }

    # Whichever seed was used, explicit or auto-discovered, the point of using
    # one is the inheritance-only art. Assert it reached the build rather than
    # trusting the input: an auto-discovered seed is never preflighted, so this
    # is the only check that covers it.
    # Check the output whether or not a seed was resolved. Gating this on
    # $seedUsed meant a genuinely unseeded build skipped it entirely and still
    # reported success while missing every inherited image -- the original bug.
    # An unseeded build is a legitimate thing to ask for, so it warns rather
    # than throwing; a seeded one that still came up short is a real failure.
    $missingInOutput = Get-MissingInheritedArt $out
    if ($missingInOutput.Count -eq 0) {
        Write-Host ("  build carries all {0} inheritance-only images" -f $inheritedOnlyImages.Count) -ForegroundColor Green
    } elseif ($seedUsed) {
        throw ("The build was seeded from '{0}' but is missing {1} of {2} inheritance-only images, first: {3}" -f `
            [string]$manifestObj.previous_build_seed.source, $missingInOutput.Count,
            $inheritedOnlyImages.Count, (($missingInOutput | Select-Object -First 3) -join ", "))
    } else {
        Write-Host ("  WARNING: no seed was resolved, so this build is missing {0} of {1} " -f `
            $missingInOutput.Count, $inheritedOnlyImages.Count) -ForegroundColor Red
        Write-Host ("           inheritance-only images (first: {0})." -f `
            (($missingInOutput | Select-Object -First 3) -join ", ")) -ForegroundColor Red
        Write-Host "           Pass -PreviousBuildDir <previous build> to inherit them." -ForegroundColor Red
    }
    if ($PreviousBuildDir) {
        $expectedSeedName = ($PreviousBuildDir.TrimEnd('/', '\') -split '[/\\]')[-1]
        $actualSeedSource = [string]$manifestObj.previous_build_seed.source
        $actualSeedName = ($actualSeedSource.TrimEnd('/', '\') -split '[/\\]')[-1]
        if ($expectedSeedName -ne $actualSeedName) {
            throw "Seed identity drift: asked for '$PreviousBuildDir' (name '$expectedSeedName') but the manifest recorded source '$actualSeedSource' (name '$actualSeedName')."
        }
        Write-Host "  seed verified: $actualSeedName" -ForegroundColor Green
    }
    if ($MobileFurnitureBehaviors) {
        # The runtime byte gates the complete implemented mobile-furniture
        # dispatcher. Restore its exact validated map set atomically; the
        # generator's base payload intentionally contains rendered-only maps.
        $behaviorMapSource = Join-Path $root "patcher_assets\optional_patches\mobile_furniture_behaviors\pc_fmaps"
        $assetDestination = Join-Path $out "Assets"
        $behaviorMaps = Get-ChildItem -LiteralPath $behaviorMapSource -Filter "*.fmap" -File
        if ($behaviorMaps.Count -ne 34) {
            throw "Expected 34 validated mobile-furniture behavior maps, found $($behaviorMaps.Count)."
        }
        foreach ($sourceMap in $behaviorMaps) {
            $targetMap = Join-Path $assetDestination $sourceMap.Name
            Copy-Item -LiteralPath $sourceMap.FullName -Destination $targetMap -Force
            if ((Get-FileHash -LiteralPath $sourceMap.FullName -Algorithm SHA256).Hash -ne
                (Get-FileHash -LiteralPath $targetMap -Algorithm SHA256).Hash) {
                throw "Mobile-furniture behavior map copy drifted: $($sourceMap.Name)"
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
    # Every optional feature behind a one-byte runtime gate is dormant in a
    # freshly linked executable: the linker writes 00 and only the offline
    # patcher flips it when the player ticks that setting. A playtest build has
    # no patcher step, so each selected gate has to be set here or the feature
    # ships present-but-off -- which is what made earlier "all enabled"
    # playtests silently omit Holiday Furniture goals, Allow Older Pregnancies,
    # the Older Villager Mortality curve, and the Store Scroll Bar.
    $linkedExe = Join-Path $out $ExeName
    $runtimeFlags = [ordered]@{
        ".vf2beh"  = @($MobileFurnitureBehaviors, "mobile furniture behaviors")
        ".vf2goal" = @($HolidayFurnitureGoals, "Holiday Furniture goals")
        ".vf2preg" = @($AllowOlderPregnancies, "Allow Older Pregnancies")
        ".vf2mort" = @($OlderVillagerMortality, "Older Villager Mortality curve")
        ".vf2scrl" = @($StoreScrollBar, "Store Scroll Bar")
    }
    foreach ($section in $runtimeFlags.Keys) {
        $selected = $runtimeFlags[$section][0]
        $label = $runtimeFlags[$section][1]
        if (-not $selected) {
            Write-Host ("  {0} left at 00 ({1} not selected)" -f $section, $label)
            continue
        }
        & $Python "work\enable_runtime_flag.py" $linkedExe $section
        if ($LASTEXITCODE -ne 0) {
            throw "Could not enable the $label runtime gate ($section) in the playtest executable."
        }
        Write-Host ("  {0} set to 01 ({1})" -f $section, $label) -ForegroundColor Green
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

# VF2 derives its save folder from the executable filename, so any build whose
# -ExeName differs from the last one silently starts an empty family instead of
# continuing the existing one. Print the exact folder this build will use, and
# say whether it already holds saves, so a name change can never be silent.
$saveRoot = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "LDW"
$saveFolder = Join-Path $saveRoot ([IO.Path]::GetFileNameWithoutExtension($ExeName))
$saveState = if (Test-Path -LiteralPath $saveFolder) {
    "that folder already exists on this build machine"
} else {
    "no such folder on this build machine"
}

Write-Host ""
Write-Host "Build OK:" -ForegroundColor Green
Write-Host "  $exe"
Write-Host "  $((Get-Item $exe).Length) bytes, SHA256 $hash"
Write-Host ""
Write-Host "  Saves: $saveFolder"
Write-Host "         VF2 derives this from the executable filename, so the same"
Write-Host "         relative path applies on whatever machine runs the build."
Write-Host "         ($saveState -- existence alone does not prove it holds a family,"
Write-Host "          and says nothing about a machine this build is handed off to.)"
Write-Host ""
Write-Host "This is a complete standalone folder ($out) -- copy the whole" -ForegroundColor Green
Write-Host "thing to hand it off; it does not need anything from outside itself." -ForegroundColor Green
Write-Host "Logs: $logDir"
