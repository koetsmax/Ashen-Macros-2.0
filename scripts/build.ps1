# Build PyInstaller output from launcher.spec
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Version = (& python "$RepoRoot\scripts\get_version.py").Trim()
Write-Host "Building version $Version"

$DistApp = Join-Path $RepoRoot "dist\Ashen Macros"
if ($Clean) {
    if (Test-Path "$RepoRoot\build") { Remove-Item -Recurse -Force "$RepoRoot\build" }
    if (Test-Path $DistApp) { Remove-Item -Recurse -Force $DistApp }
}

python -m PyInstaller "$RepoRoot\launcher.spec" --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$Exe = Join-Path $DistApp "Ashen Macros.exe"
if (-not (Test-Path $Exe)) {
    throw "Expected PyInstaller output missing: $Exe"
}

Write-Host "Built $Exe"
