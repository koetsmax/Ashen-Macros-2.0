#Requires -Version 5.1
<#
.SYNOPSIS
  Install or update Vencord + AshenMacrosBridge userplugin for Ashen Macros.

.PARAMETER Action
  install | update | updatePlugin | updateVencord | status

.PARAMETER VencordPath
  Path to the Vencord source tree (default: Documents\Vencord).

.PARAMETER PluginRepo
  Git URL for ashen-macros-vencord.

.PARAMETER SkipInject
  Skip pnpm inject (Vencord Installer UI).
#>
[CmdletBinding()]
param(
    [ValidateSet("install", "update", "updatePlugin", "updateVencord", "status")]
    [string]$Action = "install",

    [string]$VencordPath = "",

    [string]$PluginRepo = "https://github.com/koetsmax/ashen-macros-vencord.git",

    [switch]$SkipInject
)

$ErrorActionPreference = "Stop"
# pnpm/git write normal progress to stderr; do not treat that as terminating.
if (Test-Path variable:/PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$PluginFolderName = "ashenMacrosBridge"
$VencordRepo = "https://github.com/Vendicated/Vencord.git"

function Write-ProgressJson {
    param(
        [string]$Stage,
        [string]$Message,
        [bool]$Ok = $true,
        [hashtable]$Extra = $null
    )
    $obj = [ordered]@{
        stage   = $Stage
        message = $Message
        ok      = $Ok
    }
    if ($Extra) {
        foreach ($k in $Extra.Keys) {
            $obj[$k] = $Extra[$k]
        }
    }
    $json = $obj | ConvertTo-Json -Compress -Depth 6
    Write-Output $json
}

function Refresh-PathEnv {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($machine -and $user) {
        $env:Path = "$machine;$user"
    } elseif ($machine) {
        $env:Path = $machine
    } elseif ($user) {
        $env:Path = $user
    }
}

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Ensure-Winget {
    if (-not (Test-CommandExists "winget")) {
        throw "winget is not available. Install App Installer from the Microsoft Store, then retry."
    }
}

function Install-WingetPackage {
    param(
        [string]$Id,
        [string]$Label
    )
    Ensure-Winget
    Write-ProgressJson -Stage "toolchain" -Message "Installing $Label via winget ($Id)..."
    $wingetArgs = @(
        "install", "--id", $Id,
        "-e", "--accept-package-agreements", "--accept-source-agreements"
    )
    & winget @wingetArgs
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install $Label ($Id). Exit code $LASTEXITCODE. You may need to approve a UAC prompt."
    }
    Refresh-PathEnv
}

function Ensure-Toolchain {
    Refresh-PathEnv

    if (-not (Test-CommandExists "git")) {
        Install-WingetPackage -Id "Git.Git" -Label "Git"
        Refresh-PathEnv
        if (-not (Test-CommandExists "git")) {
            throw "Git was installed but is not on PATH yet. Close this window, open a new terminal, and retry."
        }
    }

    if (-not (Test-CommandExists "node")) {
        Install-WingetPackage -Id "OpenJS.NodeJS.LTS" -Label "Node.js LTS"
        Refresh-PathEnv
        if (-not (Test-CommandExists "node")) {
            throw "Node.js was installed but is not on PATH yet. Restart the app / open a new terminal and retry."
        }
    }

    $nodeVer = (& node --version 2>$null)
    if ($nodeVer -match '^v?(\d+)') {
        $major = [int]$Matches[1]
        if ($major -lt 18) {
            throw "Node.js $nodeVer found; Vencord needs Node 18+. Upgrade Node and retry."
        }
    }

    if (-not (Test-CommandExists "pnpm")) {
        if (Test-CommandExists "corepack") {
            Write-ProgressJson -Stage "toolchain" -Message "Enabling pnpm via corepack..."
            & corepack enable 2>$null
            & corepack prepare pnpm@latest --activate 2>$null
            Refresh-PathEnv
        }
        if (-not (Test-CommandExists "pnpm")) {
            Install-WingetPackage -Id "pnpm.pnpm" -Label "pnpm"
            Refresh-PathEnv
        }
        if (-not (Test-CommandExists "pnpm")) {
            throw "pnpm was installed but is not on PATH yet. Restart the app / open a new terminal and retry."
        }
    }

    $gitVer = ((& git --version) -replace '^git version ', '')
    $nodeV = & node --version
    $pnpmV = & pnpm --version
    Write-ProgressJson -Stage "toolchain" -Message ("Toolchain OK - git {0}, node {1}, pnpm {2}" -f $gitVer, $nodeV, $pnpmV)
}

function Get-DefaultVencordPath {
    return (Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Vencord")
}

function Assert-GitRepo {
    param([string]$Path)
    return (Test-Path (Join-Path $Path ".git"))
}

function Invoke-Git {
    param(
        [string]$WorkDir,
        [string[]]$GitArgs
    )
    Push-Location $WorkDir
    try {
        & git @GitArgs
        if ($LASTEXITCODE -ne 0) {
            throw ("git {0} failed (exit {1}) in {2}" -f ($GitArgs -join " "), $LASTEXITCODE, $WorkDir)
        }
    } finally {
        Pop-Location
    }
}

function Reset-ManagedGitWorktree {
    <#
      Discard local modifications to tracked files so a managed update can
      fast-forward. Does NOT run git clean (would risk deleting userplugins).
    #>
    param(
        [string]$Path,
        [string]$Label
    )
    $porcelain = & git -C $Path status --porcelain 2>$null
    if (-not $porcelain) {
        return
    }
    $lines = @($porcelain | Where-Object { $_ -and $_.Trim() })
    if ($lines.Count -eq 0) {
        return
    }
    Write-ProgressJson -Stage $Label -Message ("Discarding local changes in {0} tracked file(s) so update can proceed..." -f $lines.Count)
    # reset --hard only affects tracked files; nested userplugins clones are untouched.
    Invoke-Git -WorkDir $Path -GitArgs @("reset", "--hard", "HEAD")
}

function Merge-FastForward {
    param(
        [string]$Path,
        [string]$RemoteRef,
        [string]$Label
    )
    Reset-ManagedGitWorktree -Path $Path -Label $Label
    try {
        Invoke-Git -WorkDir $Path -GitArgs @("merge", "--ff-only", $RemoteRef)
    } catch {
        throw ("Could not fast-forward {0} to {1}. If this keeps failing, re-clone or run Setup / Repair. Details: {2}" -f $Label, $RemoteRef, $_.Exception.Message)
    }
}

function Ensure-VencordRepo {
    param(
        [string]$Path,
        [bool]$Pull
    )
    if (-not (Test-Path $Path)) {
        Write-ProgressJson -Stage "vencord" -Message "Cloning Vencord into $Path..."
        $parent = Split-Path -Parent $Path
        if ($parent -and -not (Test-Path $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        & git clone $VencordRepo $Path
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to clone Vencord. Check your network and retry."
        }
        return
    }

    if (-not (Assert-GitRepo $Path)) {
        $childCount = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue).Count
        if ($childCount -eq 0) {
            Write-ProgressJson -Stage "vencord" -Message "Empty folder at $Path - cloning Vencord into it..."
            & git clone $VencordRepo $Path
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to clone Vencord into empty folder. Check your network and retry."
            }
            return
        }
        throw "Path exists but is not a git repo: $Path. Choose an empty folder or an existing Vencord clone."
    }

    if ($Pull) {
        Write-ProgressJson -Stage "vencord" -Message "Updating Vencord (git fetch + pull)..."
        Invoke-Git -WorkDir $Path -GitArgs @("fetch", "--prune", "origin")
        $branch = (& git -C $Path rev-parse --abbrev-ref HEAD).Trim()
        $remoteRef = $null
        $upstream = (& git -C $Path rev-parse --abbrev-ref '@{u}' 2>$null)
        if ($LASTEXITCODE -eq 0 -and $upstream) {
            $remoteRef = $upstream.Trim()
        } else {
            & git -C $Path rev-parse --verify "origin/main" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $remoteRef = "origin/main"
            } else {
                & git -C $Path rev-parse --verify "origin/dev" 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    $remoteRef = "origin/dev"
                }
            }
        }
        if ($remoteRef) {
            Merge-FastForward -Path $Path -RemoteRef $remoteRef -Label "vencord"
        } else {
            Write-ProgressJson -Stage "vencord" -Message "No remote tracking branch found; skipped pull." -Ok $true
        }
        $sha = (& git -C $Path rev-parse --short HEAD).Trim()
        Write-ProgressJson -Stage "vencord" -Message ("Vencord at {0} ({1})" -f $branch, $sha)
    } else {
        Write-ProgressJson -Stage "vencord" -Message "Using existing Vencord at $Path"
    }
}

function Ensure-PluginRepo {
    param(
        [string]$VencordRoot,
        [string]$RepoUrl,
        [bool]$Pull
    )
    $userplugins = Join-Path $VencordRoot "src\userplugins"
    if (-not (Test-Path $userplugins)) {
        New-Item -ItemType Directory -Path $userplugins -Force | Out-Null
    }
    $pluginPath = Join-Path $userplugins $PluginFolderName

    if (-not (Test-Path $pluginPath)) {
        Write-ProgressJson -Stage "plugin" -Message "Cloning AshenMacrosBridge into $pluginPath..."
        & git clone $RepoUrl $pluginPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to clone the plugin repo. Sign in to GitHub (Git Credential Manager or: gh auth login), ensure you have access to koetsmax/ashen-macros-vencord, then retry."
        }
        return $pluginPath
    }

    if (-not (Assert-GitRepo $pluginPath)) {
        throw "Plugin folder exists but is not a git clone: $pluginPath. Remove or rename it and re-run Setup so it can be cloned from GitHub."
    }

    if ($Pull) {
        Write-ProgressJson -Stage "plugin" -Message "Updating plugin (git fetch + pull)..."
        try {
            Invoke-Git -WorkDir $pluginPath -GitArgs @("fetch", "--prune", "origin")
            $upstream = (& git -C $pluginPath rev-parse --abbrev-ref '@{u}' 2>$null)
            if ($LASTEXITCODE -eq 0 -and $upstream) {
                Merge-FastForward -Path $pluginPath -RemoteRef $upstream.Trim() -Label "plugin"
            } else {
                $fallback = $null
                foreach ($c in @("origin/main", "origin/master")) {
                    & git -C $pluginPath rev-parse --verify $c 2>$null | Out-Null
                    if ($LASTEXITCODE -eq 0) { $fallback = $c; break }
                }
                if ($fallback) {
                    Merge-FastForward -Path $pluginPath -RemoteRef $fallback -Label "plugin"
                }
            }
        } catch {
            throw ("Failed to update the plugin repo. Sign in to GitHub (Git Credential Manager or: gh auth login) and retry. {0}" -f $_.Exception.Message)
        }
    } else {
        Write-ProgressJson -Stage "plugin" -Message "Using existing plugin at $pluginPath"
    }

    return $pluginPath
}

function Get-PluginVersion {
    param([string]$PluginPath)
    $pkg = Join-Path $PluginPath "package.json"
    if (-not (Test-Path $pkg)) { return $null }
    try {
        $raw = Get-Content -Raw -Path $pkg | ConvertFrom-Json
        return [string]$raw.version
    } catch {
        return $null
    }
}

function Invoke-Pnpm {
    param(
        [string]$WorkDir,
        [string[]]$PnpmArgs,
        [string]$Stage,
        [string]$Label
    )
    Write-ProgressJson -Stage $Stage -Message $Label
    Push-Location $WorkDir
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        # Capture stdout+stderr as text. pnpm prints the script cmdline to stderr;
        # with PSNativeCommandUseErrorActionPreference that must not abort us.
        $output = & pnpm @PnpmArgs 2>&1
        $code = $LASTEXITCODE
        $lines = @()
        foreach ($line in @($output)) {
            if ($null -eq $line) { continue }
            $text = $null
            if ($line -is [System.Management.Automation.ErrorRecord]) {
                # Blank stderr lines become RemoteException with an empty message.
                $text = [string]$line.Exception.Message
                if ([string]::IsNullOrWhiteSpace($text)) {
                    $text = [string]$line.ToString()
                }
                if (
                    [string]::IsNullOrWhiteSpace($text) -or
                    $text -eq "System.Management.Automation.RemoteException"
                ) {
                    continue
                }
            } else {
                $text = [string]$line
            }
            $text = $text.Trim()
            if (-not $text) { continue }
            $lines += $text
            Write-ProgressJson -Stage $Stage -Message $text
        }
        if ($code -ne 0) {
            $tail = ($lines | Select-Object -Last 12) -join " | "
            if (-not $tail) { $tail = "(no output)" }
            throw ("pnpm {0} failed (exit {1}). Last output: {2}" -f ($PnpmArgs -join " "), $code, $tail)
        }
    } finally {
        $ErrorActionPreference = $prevEap
        Pop-Location
    }
}

function Build-Vencord {
    param([string]$Path)
    Invoke-Pnpm -WorkDir $Path -PnpmArgs @("install", "--frozen-lockfile") -Stage "build" -Label "pnpm install --frozen-lockfile..."
    Invoke-Pnpm -WorkDir $Path -PnpmArgs @("build") -Stage "build" -Label "pnpm build..."
}

function Invoke-Inject {
    param([string]$Path)
    Write-ProgressJson -Stage "inject" -Message "Opening a separate terminal for the Vencord Installer (arrow keys + Enter). Patch Discord, then close that terminal when finished..."

    # Interactive TUI cannot run under a piped process - use a visible console.
    $tempPs1 = Join-Path ([System.IO.Path]::GetTempPath()) ("ashen-vencord-inject-" + [guid]::NewGuid().ToString("n") + ".ps1")
    $pathLiteral = $Path.Replace("'", "''")
    $script = @"
`$ErrorActionPreference = 'Continue'
if (Test-Path variable:/PSNativeCommandUseErrorActionPreference) {
    `$PSNativeCommandUseErrorActionPreference = `$false
}
Set-Location -LiteralPath '$pathLiteral'
Write-Host ''
Write-Host 'Ashen Macros - Vencord Installer' -ForegroundColor Cyan
Write-Host 'Use arrow keys to select Discord, Enter to patch, then close this window.' -ForegroundColor Cyan
Write-Host ''
pnpm inject
`$code = `$LASTEXITCODE
if (`$code -ne 0) {
    Write-Host ''
    Write-Host ("pnpm inject exited with code " + `$code) -ForegroundColor Yellow
    Write-Host 'Press any key to close...'
    try { `$null = `$Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { Start-Sleep -Seconds 3 }
}
exit `$code
"@
    try {
        Set-Content -LiteralPath $tempPs1 -Value $script -Encoding UTF8
        $proc = Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $tempPs1
        ) -WorkingDirectory $Path -Wait -PassThru
        $exitCode = 0
        if ($null -ne $proc) { $exitCode = [int]$proc.ExitCode }

        if ($exitCode -ne 0) {
            Write-ProgressJson -Stage "inject" -Message ("Vencord Installer exited with code {0}. If Discord was not patched, run Setup again." -f $exitCode) -Ok $false
        } else {
            Write-ProgressJson -Stage "inject" -Message "Vencord Installer finished."
        }
    } finally {
        Remove-Item -LiteralPath $tempPs1 -Force -ErrorAction SilentlyContinue
    }
}

function Write-PostSteps {
    # UI shows a friendly checklist on success; keep a short machine-readable marker.
    Write-ProgressJson -Stage "post" -Message "next_steps"
}

function Get-StatusInfo {
    param([string]$Path)
    $info = @{
        vencord_path   = $Path
        vencord_exists = (Test-Path $Path)
        vencord_sha    = $null
        vencord_behind = $null
        plugin_path    = $null
        plugin_version = $null
        plugin_sha     = $null
    }

    if ($info.vencord_exists -and (Assert-GitRepo $Path)) {
        $sha = (& git -C $Path rev-parse --short HEAD 2>$null)
        if ($sha) { $info.vencord_sha = $sha.Trim() }
        try {
            & git -C $Path fetch --prune origin 2>$null | Out-Null
            $upstream = (& git -C $Path rev-parse --abbrev-ref '@{u}' 2>$null)
            $ref = $null
            if ($LASTEXITCODE -eq 0 -and $upstream) {
                $ref = $upstream.Trim()
            } else {
                & git -C $Path rev-parse --verify "origin/main" 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) { $ref = "origin/main" }
            }
            if ($ref) {
                $behind = (& git -C $Path rev-list --count "HEAD..$ref" 2>$null)
                if ($behind -match '^\d+$') { $info.vencord_behind = [int]$behind }
            }
        } catch { }
    }

    $pluginPath = Join-Path $Path "src\userplugins\$PluginFolderName"
    if (Test-Path $pluginPath) {
        $info.plugin_path = $pluginPath
        $info.plugin_version = Get-PluginVersion $pluginPath
        if (Assert-GitRepo $pluginPath) {
            $psha = (& git -C $pluginPath rev-parse --short HEAD 2>$null)
            if ($psha) { $info.plugin_sha = $psha.Trim() }
        }
    }

    Write-ProgressJson -Stage "status" -Message "Status collected." -Extra $info
}

# --- main ---
try {
    if (-not $VencordPath) {
        $VencordPath = Get-DefaultVencordPath
    }
    $VencordPath = [System.IO.Path]::GetFullPath($VencordPath)

    Write-ProgressJson -Stage "start" -Message ("Action={0} path={1}" -f $Action, $VencordPath)

    if ($Action -eq "status") {
        if (Test-CommandExists "git") {
            Get-StatusInfo -Path $VencordPath
        } else {
            Write-ProgressJson -Stage "status" -Message "git not installed" -Ok $false -Extra @{
                vencord_path   = $VencordPath
                vencord_exists = (Test-Path $VencordPath)
            }
        }
        Write-ProgressJson -Stage "done" -Message "Done." -Extra @{ action = $Action }
        exit 0
    }

    Ensure-Toolchain

    $pullVencord = $Action -in @("install", "update", "updateVencord")
    $pullPlugin = $Action -in @("install", "update", "updatePlugin")

    if ($Action -eq "updatePlugin" -and -not (Test-Path $VencordPath)) {
        throw "Vencord path not found: $VencordPath. Run Setup / Repair first."
    }
    if ($Action -eq "updateVencord" -and -not (Test-Path $VencordPath)) {
        throw "Vencord path not found: $VencordPath. Run Setup / Repair first."
    }

    Ensure-VencordRepo -Path $VencordPath -Pull:($pullVencord)
    $null = Ensure-PluginRepo -VencordRoot $VencordPath -RepoUrl $PluginRepo -Pull:($pullPlugin)

    Build-Vencord -Path $VencordPath

    $doInject = -not $SkipInject
    if ($Action -eq "updatePlugin") {
        $distAlt = Join-Path $VencordPath "dist"
        if (Test-Path $distAlt) {
            $doInject = $false
            Write-ProgressJson -Stage "inject" -Message "Skipped inject (plugin-only update). Fully restart Discord to load the new build."
        }
    }

    if ($doInject) {
        Invoke-Inject -Path $VencordPath
    }

    Write-PostSteps

    $ver = Get-PluginVersion (Join-Path $VencordPath "src\userplugins\$PluginFolderName")
    Write-ProgressJson -Stage "done" -Message "Done." -Extra @{
        action         = $Action
        vencord_path   = $VencordPath
        plugin_version = $ver
    }
    exit 0
}
catch {
    $msg = $_.Exception.Message
    if (-not $msg) { $msg = "$_" }
    Write-ProgressJson -Stage "error" -Message $msg -Ok $false
    exit 1
}
