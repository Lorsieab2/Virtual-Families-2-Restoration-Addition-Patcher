$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $root "VF2-Native-Rebuild-Prototype-Source.cs"
$output = Join-Path $root "VF2-Native-Rebuild-Prototype.exe"
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if (-not (Test-Path $csc)) {
    throw "Could not find the .NET Framework C# compiler at $csc"
}

& $csc /nologo /target:winexe /platform:x64 /optimize+ `
    /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll `
    /out:$output $source

Write-Host "Built $output"
Write-Host "Run with --write-sample-save to emit com.ldw.virtualfamilies2 save files beside the EXE."
