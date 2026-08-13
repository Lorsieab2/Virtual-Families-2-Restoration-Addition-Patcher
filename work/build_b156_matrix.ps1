param(
    [string]$Python = "",
    [ValidateRange(0, 15)]
    [int]$StartMask = 0
)

$ErrorActionPreference = "Stop"
$matrixBuilder = Join-Path $PSScriptRoot "build_b155_5_matrix.ps1"
& $matrixBuilder `
    -Python $Python `
    -StartMask $StartMask `
    -BuildLabel "B156" `
    -PreviousBuildLabel "B155.5"
