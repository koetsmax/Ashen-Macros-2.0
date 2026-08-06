# Build the first-install Inno Setup installer.
param(
    [string]$Version = "",
    [string]$IsccPath = ""
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

if ([string]::IsNullOrWhiteSpace($IsccPath)) {
    $candidates = @(
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            $IsccPath = (Get-Command $candidate).Source
            break
        }
        if (Test-Path $candidate) {
            $IsccPath = $candidate
            break
        }
    }
}

if ([string]::IsNullOrWhiteSpace($IsccPath) -or -not (Test-Path $IsccPath)) {
    throw "Inno Setup compiler (ISCC.exe) not found. Install Inno Setup 6 or pass -IsccPath."
}

$Iss = Join-Path $RepoRoot "installer\ashen-macros.iss"
& $IsccPath "/DMyAppVersion=$Version" $Iss
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit code $LASTEXITCODE" }

$Installer = Join-Path $RepoRoot "dist\Ashen.Macro.installer.exe"
if (-not (Test-Path $Installer)) {
    throw "Expected installer missing: $Installer"
}
Write-Host "Built $Installer"
