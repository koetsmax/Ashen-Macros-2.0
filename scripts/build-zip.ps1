# Zip PyInstaller dist\Ashen Macros for in-app updates.
param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = (& python "$RepoRoot\scripts\get_version.py").Trim()
}

$Source = Join-Path $RepoRoot "dist\Ashen Macros"
if (-not (Test-Path $Source)) {
    throw "Missing PyInstaller output at $Source. Run scripts\build.ps1 first."
}

$DistDir = Join-Path $RepoRoot "dist"
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

$ZipName = "Ashen-Macros-$Version.zip"
$ZipPath = Join-Path $DistDir $ZipName
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }

# Zip contents so extract-over-install_dir works (flat layout).
Compress-Archive -Path (Join-Path $Source "*") -DestinationPath $ZipPath -Force
Write-Host "Created $ZipPath"
