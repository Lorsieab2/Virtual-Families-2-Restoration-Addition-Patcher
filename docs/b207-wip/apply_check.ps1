# Import check, default apply and Owner's Defaults apply of a release zip, each into a new scratch folder.
param(
    [Parameter(Mandatory = $true)] [string]$Zip,
    [Parameter(Mandatory = $true)] [string]$Release,      # B207
    [Parameter(Mandatory = $true)] [string]$Base,         # new folder, e.g. C:\vf2w\b207-check-<date>
    [string]$Checkout = "C:\vf2w\b202-release"
)
$ErrorActionPreference = "Stop"
$py = "C:\Users\Owner\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path $Base) { throw "$Base already exists; use a new folder" }
New-Item -ItemType Directory $Base | Out-Null

function Unzip($dest) {
    New-Item -ItemType Directory $dest | Out-Null
    Expand-Archive -LiteralPath $Zip -DestinationPath $dest
    return (Get-ChildItem $dest -Directory | Select-Object -First 1).FullName
}

# 1. Import check from an empty unzip folder: every .py of the patcher files folder imports from the bundle.
$u = Unzip (Join-Path $Base "unzip-import")
$pf = Join-Path $u "Virtual Families 2 Fun Patcher Files"
$mods = Get-ChildItem $pf -Filter *.py | ForEach-Object { $_.BaseName }
$ok = 0; $bad = @()
foreach ($m in $mods) {
    $code = "import sys; sys.path.insert(0, r'$pf'); import $m; f = getattr(sys.modules['$m'], '__file__', ''); assert f.lower().startswith(r'$pf'.lower()), f"
    Push-Location $Base
    & $py -I -c $code 2>&1 | Out-Null
    $rc = $LASTEXITCODE
    Pop-Location
    if ($rc -eq 0) { $ok++ } else { $bad += $m }
}
"IMPORT CHECK: $ok of $($mods.Count) modules import from the bundle; failed: $($bad -join ', ')"

function Apply($name, [string[]]$extra) {
    $root = Join-Path $Base $name
    $uz = Unzip (Join-Path $root "unzip") | Select-Object -Last 1
    $pfa = Join-Path $uz "Virtual Families 2 Fun Patcher Files"
    $game = Join-Path $root "Virtual Families 2"
    New-Item -ItemType Directory $game | Out-Null
    $src = Join-Path $Checkout "work\vanilla_runtime_payload"
    robocopy $src $game /E /XF *.id0 *.id1 *.id2 *.nam *.til /NFL /NDL /NJH /NJS /NP | Out-Null
    $log = Join-Path $root "apply.log"
    $args2 = @("-I", (Join-Path $pfa "offline_vf2_patcher.py"), "apply", "--exe", (Join-Path $game "Virtual Families 2.exe"),
               "--manifest", (Join-Path $pfa "manifest.json"), "--output-parent-dir", $root) + $extra
    & $py @args2 *> $log
    Write-Host "APPLY $name exit $LASTEXITCODE (log $log)"
    Select-String -Path $log -Pattern "^(Enabled settings|Disabled settings|Selected but inactive|Patched files)" | ForEach-Object { Write-Host ("  " + $_.Line) }
    $exe = Get-ChildItem (Join-Path $root "VF2-$Release-Modded") -Filter "Virtual Families 2 - Modded $Release.exe" | Select-Object -First 1
    if ($exe) {
        Write-Host "  exe: $($exe.FullName)  sha256 $((Get-FileHash $exe.FullName).Hash)"
        & $py (Join-Path $here "emulate_store_pages.py") $Checkout $exe.FullName | Out-Host
    } else { Write-Host "  NO MODDED EXE" }
    return $pfa
}

$pfDefault = Apply "default" @()
$owners = & $py -I (Join-Path $here "owners_defaults.py") $pfDefault (Join-Path $pfDefault "manifest.json") owners
"OWNER'S DEFAULTS selection: $owners"
$null = Apply "owners" @("--disable-all", "--enable", $owners)


