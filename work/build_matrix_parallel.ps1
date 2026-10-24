# Build the variant matrix as N parallel parts, one per worktree, with the unchanged
# work/build_matrix.ps1 doing every build. This is how the B202 matrix was built by hand
# ("run as three parallel thirds in three worktrees of that one commit", docs/b202-matrix-manifest.md);
# this script does the same thing the same way every time.
#
# Why worktrees: the generator writes work/patched_mobile_furniture_pack_objs, so one checkout can
# build one variant at a time. Each worktree builds its own share of the variants into its own outputs\.
#
#   powershell -File work\build_matrix_parallel.ps1 -Python <python.exe> `
#       -MatrixConfig data\vf2\build-matrix-toggles.json -ReleaseConfig data\vf2\build-matrix-release-bNNN.json `
#       -Worktrees C:\vf2w\bNNN-m1,C:\vf2w\bNNN-m2,C:\vf2w\bNNN-m3 [-CollectInto C:\vf2w\bNNN-release]
#
# Every worktree must be at the same commit as this checkout with no tracked changes, and must already
# hold the gitignored build inputs (work\vanilla_runtime_payload, and the seed folders the release config
# names under outputs\). Variants are dealt out in matrix order, variant i to part (i mod N), so the split
# is the same every run. Part k writes outputs\<prefix>-summary-m<k>.json and outputs\<prefix>-logs-m<k>,
# the names the B202 parts used. Nothing about what is built changes: each part runs build_matrix.ps1 with
# a matrix file that holds only its own variants, and the toggles of every variant are copied unchanged.
#
# -PlanOnly checks the worktrees, writes the part matrix files and prints the split, and builds nothing.
# -CollectOnly builds nothing and only collects parts an earlier run built (use it with -CollectInto);
# work\release_parallel.ps1 uses it so the matrix folders reach the release checkout only after its early
# test run has finished (tests there glob outputs\ for matrix folders and manifests).
# -CollectInto copies every variant folder, summary and log folder into that checkout's outputs\ (it
# refuses to overwrite anything already there) and checks that all variants arrived with distinct hashes.
param(
    [Parameter(Mandatory = $true)] [string]$Python,
    [Parameter(Mandatory = $true)] [string]$MatrixConfig,
    [Parameter(Mandatory = $true)] [string]$ReleaseConfig,
    [Parameter(Mandatory = $true)] [string[]]$Worktrees,
    [string]$CollectInto,
    [switch]$PlanOnly,
    [switch]$CollectOnly
)

$ErrorActionPreference = "Stop"
# powershell -File passes a comma list as one string.
$Worktrees = @($Worktrees | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$head = (& git -C $root rev-parse HEAD).Trim()
$matrixPath = (Resolve-Path -LiteralPath $MatrixConfig).Path
$releasePath = (Resolve-Path -LiteralPath $ReleaseConfig).Path
$matrixRel = $matrixPath.Substring($root.Length).TrimStart('\')
$releaseRel = $releasePath.Substring($root.Length).TrimStart('\')
$matrix = Get-Content -LiteralPath $matrixPath -Raw | ConvertFrom-Json
$release = Get-Content -LiteralPath $releasePath -Raw | ConvertFrom-Json
$prefix = $release.output_prefix
$variants = @($matrix.variants)
$parts = $Worktrees.Count
if ($parts -lt 1) { throw "Name at least one worktree." }

foreach ($wt in $Worktrees) {
    $wtHead = (& git -C $wt rev-parse HEAD).Trim()
    if ($wtHead -ne $head) { throw "$wt is at $wtHead, not $head (this checkout)." }
    $dirty = & git -C $wt status --porcelain --untracked-files=no
    if ($dirty) { throw "$wt has tracked changes:`n$($dirty -join "`n")" }
    if (-not (Test-Path -LiteralPath (Join-Path $wt "work\vanilla_runtime_payload") -PathType Container)) {
        throw "$wt has no work\vanilla_runtime_payload."
    }
    foreach ($name in @("$prefix-logs", "$prefix-summary.json")) {
        if ($CollectOnly) { break }
        if (Test-Path -LiteralPath (Join-Path $wt "outputs\$name")) { throw "$wt already holds outputs\$name." }
    }
}

# The link step needs Windows' find.exe ahead of any Unix find (README, Development), and every part
# inherits this process's environment.
$env:PATH = 'C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem'

$partDir = Join-Path ([IO.Path]::GetTempPath()) ("vf2-matrix-parts-" + [Guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $partDir | Out-Null
$jobs = @()
for ($k = 0; $k -lt $parts; $k++) {
    $mine = @(for ($i = $k; $i -lt $variants.Count; $i += $parts) { $variants[$i] })
    $copy = $matrix | ConvertTo-Json -Depth 20 | ConvertFrom-Json
    $copy.variants = $mine
    $partFile = Join-Path $partDir "matrix-m$($k + 1).json"
    $copy | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $partFile -Encoding UTF8
    $wt = $Worktrees[$k]
    $log = Join-Path $partDir "build-m$($k + 1).log"
    Write-Host "m$($k + 1): $($mine.Count) variants in $wt ($($mine.name -join ', '))"
    if ($PlanOnly) { continue }
    if ($CollectOnly) { $jobs += [pscustomobject]@{ part = $k + 1; worktree = $wt; log = $null; process = $null }; continue }
    $script = Join-Path $wt "work\build_matrix.ps1"
    $argsList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$script`"", "-Python", "`"$Python`"",
                  "-MatrixConfig", "`"$partFile`"", "-ReleaseConfig", "`"$(Join-Path $wt $releaseRel)`"")
    $jobs += [pscustomobject]@{
        part = $k + 1; worktree = $wt; log = $log
        process = Start-Process (Join-Path $PSHOME "powershell.exe") -ArgumentList $argsList -WorkingDirectory $wt -PassThru -NoNewWindow `
            -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    }
}
if ($PlanOnly) { Write-Host "Plan only: part matrix files are in $partDir"; return }
$jobs | Where-Object { $_.process } | ForEach-Object { $_.process.WaitForExit() }

$failed = @($jobs | Where-Object { $_.process -and $_.process.ExitCode -ne 0 })
foreach ($job in @($jobs | Where-Object { $_.process })) {
    $out = Join-Path $job.worktree "outputs"
    if (Test-Path -LiteralPath (Join-Path $out "$prefix-summary.json")) {
        Rename-Item -LiteralPath (Join-Path $out "$prefix-summary.json") -NewName "$prefix-summary-m$($job.part).json"
    }
    if (Test-Path -LiteralPath (Join-Path $out "$prefix-logs")) {
        Rename-Item -LiteralPath (Join-Path $out "$prefix-logs") -NewName "$prefix-logs-m$($job.part)"
    }
    Write-Host "m$($job.part): exit $($job.process.ExitCode), log $($job.log)"
}
if ($failed) { throw "Matrix part(s) failed: $(($failed | ForEach-Object { "m$($_.part)" }) -join ', '). Read the logs above." }

if ($CollectInto) {
    $dest = Join-Path $CollectInto "outputs"
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    $results = @()
    foreach ($job in $jobs) {
        $out = Join-Path $job.worktree "outputs"
        $summary = Get-Content -LiteralPath (Join-Path $out "$prefix-summary-m$($job.part).json") -Raw | ConvertFrom-Json
        $results += @($summary)
        $names = @($summary | ForEach-Object { "$prefix-$($_.name)" }) + @("$prefix-logs-m$($job.part)", "$prefix-summary-m$($job.part).json")
        foreach ($name in $names) {
            $target = Join-Path $dest $name
            if (Test-Path -LiteralPath $target) { throw "Refusing to overwrite $target" }
            $source = Join-Path $out $name
            if (Test-Path -LiteralPath $source -PathType Container) {
                & robocopy $source $target /E /NFL /NDL /NJH /NJS /NP | Out-Null
                if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE) copying $source" }
            } else {
                Copy-Item -LiteralPath $source -Destination $target
            }
        }
    }
    if ($results.Count -ne $variants.Count) { throw "Collected $($results.Count) variants, the matrix has $($variants.Count)." }
    $distinct = ($results | Select-Object -ExpandProperty sha256 -Unique).Count
    if ($distinct -ne $results.Count) { throw "Expected $($results.Count) byte-distinct executables, got $distinct." }
    Write-Host "Collected $($results.Count) variants into $dest, $distinct distinct hashes."
}
