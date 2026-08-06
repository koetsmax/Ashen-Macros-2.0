# Full release entry point: build, zip, optional installer, auto-create and push tag.
param(
    [ValidateSet("none", "train", "rev")]
    [string]$Bump = "none",
    [switch]$Prerelease,
    [switch]$SkipInstaller,
    [switch]$SkipPush,
    [switch]$SkipTag
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ($Bump -ne "none") {
    Write-Host "Bumping version ($Bump)..."
    & python "$RepoRoot\scripts\bump_version.py" "--$Bump"
    if ($LASTEXITCODE -ne 0) { throw "bump_version failed" }
}

$Version = (& python "$RepoRoot\scripts\get_version.py").Trim()
$Tag = (& python "$RepoRoot\scripts\get_version.py" --tag).Trim()
$Channel = if ($Prerelease) { "prerelease" } else { "latest" }
Write-Host "Releasing $Version (tag $Tag, channel $Channel)"

& "$RepoRoot\scripts\build.ps1" -Clean
& "$RepoRoot\scripts\build-zip.ps1" -Version $Version

if (-not $SkipInstaller) {
    try {
        & "$RepoRoot\scripts\build-installer.ps1" -Version $Version
    } catch {
        Write-Warning "Installer build skipped/failed: $_"
        Write-Warning "Update zip was still created. Pass -SkipInstaller to silence this."
    }
}

if (-not $SkipTag) {
    $existing = git tag -l $Tag
    if ($existing) {
        throw "Tag $Tag already exists. Bump with -Bump rev (or train) before releasing."
    }

    $ReleaseMessage = if ($Prerelease) {
        "Release $Version (prerelease)"
    } else {
        "Release $Version"
    }

    git add version
    $status = git status --porcelain
    if ($status) {
        git commit -m $ReleaseMessage
    }

    git tag -a $Tag -m $ReleaseMessage
    Write-Host "Created tag $Tag"

    if (-not $SkipPush) {
        git push origin HEAD
        git push origin $Tag
        Write-Host "Pushed branch and tag $Tag"
    } else {
        Write-Host "SkipPush set; tag created locally only."
    }
}

Write-Host "Release artifacts in dist\:"
Get-ChildItem "$RepoRoot\dist" -File | ForEach-Object { Write-Host " - $($_.Name)" }
