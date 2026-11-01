# Helpers for work\build_matrix_parallel.ps1: how the variant matrix is split over N parts, and how each
# part gets the seed folders (the previous release's matrix outputs) its own variants need.
# Dot-source it:  . (Join-Path $PSScriptRoot "matrix_parts.ps1")
# tests\test_matrix_parts.py calls these functions directly.

# Variant i goes to part (i mod N), so part sizes differ by at most one and the split is the same every
# run. With three parts this is exactly the B202-B205 split.
function Split-MatrixVariants {
    param([object[]]$Variants, [int]$Parts)
    if ($Parts -lt 1) { throw "Name at least one worktree." }
    if ($Parts -gt $Variants.Count) {
        throw "$Parts parts for $($Variants.Count) variants: at least one part would build nothing."
    }
    $split = New-Object System.Collections.ArrayList
    for ($k = 0; $k -lt $Parts; $k++) {
        $mine = New-Object System.Collections.ArrayList
        for ($i = $k; $i -lt $Variants.Count; $i += $Parts) { [void]$mine.Add($Variants[$i]) }
        [void]$split.Add($mine.ToArray())
    }
    return , $split.ToArray()
}

# The seed folders a part's variants are configured with: one entry per seeded variant, in matrix order.
function Get-PartSeeds {
    param($Release, [object[]]$Variants)
    if (-not $Release.seeds) { return @() }
    $names = @($Release.seeds.PSObject.Properties.Name)
    $seeds = @()
    foreach ($variant in $Variants) {
        if ($names -contains $variant.name) {
            $seeds += [pscustomobject]@{ variant = $variant.name; seed = [string]$Release.seeds.($variant.name) }
        }
    }
    return $seeds
}

function Get-SeedTreeStats {
    param([string]$Path)
    $files = @(Get-ChildItem -LiteralPath $Path -Recurse -File -Force)
    $bytes = ($files | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $bytes) { $bytes = 0 }
    return "$($files.Count) files, $bytes bytes"
}

# Makes sure every seed this part needs is in its own worktree before it starts. build_matrix.ps1 runs in
# the worktree, so a relative seed path ("outputs/VF2-B205-matrix-core") is read from that worktree's
# outputs\. A missing seed is copied from -SeedsFrom (the checkout that collected the previous matrix) under
# a temporary name and renamed only once it is complete and matches its source, so a copy that was cut short
# never looks like a seed. A seed already there is checked against its source and never replaced or
# changed: a mismatch stops the run. Nothing is deleted. Absolute seed paths are shared read-only by every
# part (the generator only copies out of a seed) and are only checked to exist.
# Returns one line per seed saying what was done.
function Sync-PartSeeds {
    param([string]$Worktree, [object[]]$Seeds, [string]$SeedsFrom, [switch]$CheckOnly)
    $done = @()
    foreach ($entry in $Seeds) {
        $relative = $entry.seed -replace '/', '\'
        if ([IO.Path]::IsPathRooted($relative)) {
            if (-not (Test-Path -LiteralPath $relative -PathType Container)) {
                throw "Seed $relative for $($entry.variant) does not exist."
            }
            $done += "$($entry.variant): shared $relative"
            continue
        }
        $target = Join-Path $Worktree $relative
        $source = $null
        if ($SeedsFrom) {
            $source = Join-Path $SeedsFrom $relative
            if (-not (Test-Path -LiteralPath $source -PathType Container)) {
                throw "-SeedsFrom $SeedsFrom has no $relative (seed for $($entry.variant))."
            }
        }
        $sameFolder = $source -and ([IO.Path]::GetFullPath($source).TrimEnd('\') -ieq [IO.Path]::GetFullPath($target).TrimEnd('\'))
        if (Test-Path -LiteralPath $target) {
            if ($source -and -not $sameFolder) {
                $have = Get-SeedTreeStats $target
                $want = Get-SeedTreeStats $source
                if ($have -ne $want) {
                    throw "$target ($have) differs from $source ($want). Move it aside and run again."
                }
            }
            $done += "$($entry.variant): present in $Worktree"
            continue
        }
        if (-not $source) {
            throw "$Worktree has no $relative (seed for $($entry.variant)). Pass -SeedsFrom <checkout holding it>."
        }
        if ($CheckOnly) { $done += "$($entry.variant): would copy $source"; continue }
        $parent = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        $leaf = Split-Path -Leaf $target
        $partial = Join-Path $parent ("$leaf.partial-" + [Guid]::NewGuid().ToString("N").Substring(0, 8))
        & robocopy $source $partial /E /NFL /NDL /NJH /NJS /NP /R:2 /W:1 | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE) copying $source to $partial" }
        $have = Get-SeedTreeStats $partial
        $want = Get-SeedTreeStats $source
        if ($have -ne $want) { throw "Copy of $source is incomplete ($have, want $want); left at $partial" }
        Rename-Item -LiteralPath $partial -NewName $leaf
        $done += "$($entry.variant): copied from $source"
    }
    return $done
}
