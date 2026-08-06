"""Release checks and zip-based in-app updates."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

import requests
from packaging import version

logger = logging.getLogger(__name__)

GITHUB_RELEASES_LATEST = (
    "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases/latest"
)
GITHUB_RELEASES_LIST = (
    "https://api.github.com/repos/koetsmax/ashen-macros-2.0/releases"
)
GITHUB_DOWNLOAD_BASE = (
    "https://github.com/koetsmax/Ashen-Macros-2.0/releases/download"
)

# Process names used by the installed / built launcher (without .exe for Stop-Process).
LAUNCHER_PROCESS_BASENAMES = (
    "launcher",
    "Ashen Macros",
)

# Survive parent exit when the launcher is in a Windows job object (common with PyInstaller).
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_CREATE_NEW_PROCESS_GROUP = 0x00000200

UPDATE_HELPER_PS1 = r"""param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$StagingDir,
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [Parameter(Mandatory = $true)][string]$AppExe
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Only one apply at a time — a second helper must not Stop-Process the
# instance the first helper already relaunched.
$mutex = New-Object System.Threading.Mutex($false, "Global\AshenMacrosZipUpdate")
$taken = $false
$form = $null
try {
    $taken = $mutex.WaitOne([TimeSpan]::FromMinutes(5))
    if (-not $taken) { exit 1 }

    # Another helper already applied and deleted staging.
    if (-not (Test-Path -LiteralPath $StagingDir)) { exit 0 }

    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt 120) {
        try {
            Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
            Start-Sleep -Milliseconds 250
        } catch {
            break
        }
    }
    # Kill only the waited-for process if it hung — never all "Ashen Macros"
    # by name (that races with a newly relaunched instance).
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    } catch {}
    Start-Sleep -Seconds 1

    $payload = $StagingDir
    $children = @(Get-ChildItem -LiteralPath $StagingDir -ErrorAction SilentlyContinue)
    if (($children.Count -eq 1) -and $children[0].PSIsContainer) {
        $payload = $children[0].FullName
    }

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Installing Ashen Macros"
    $form.Size = New-Object System.Drawing.Size(420, 150)
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.ControlBox = $false
    $form.TopMost = $true

    $label = New-Object System.Windows.Forms.Label
    $label.Text = "Installing update..."
    $label.AutoSize = $true
    $label.Location = New-Object System.Drawing.Point(16, 18)

    $bar = New-Object System.Windows.Forms.ProgressBar
    $bar.Location = New-Object System.Drawing.Point(16, 52)
    $bar.Size = New-Object System.Drawing.Size(370, 24)
    $bar.Minimum = 0
    $bar.Maximum = 100
    $bar.Style = [System.Windows.Forms.ProgressBarStyle]::Continuous

    $form.Controls.Add($label)
    $form.Controls.Add($bar)
    $form.Show()
    $form.Refresh()
    [System.Windows.Forms.Application]::DoEvents()

    try {
        $files = @(Get-ChildItem -LiteralPath $payload -Recurse -File -ErrorAction Stop)
        $total = $files.Count
        if ($total -le 0) {
            throw "Update staging has no files to install."
        }

        $stagingRoot = [IO.Path]::GetFullPath($payload).TrimEnd('\')
        $i = 0
        foreach ($file in $files) {
            $full = [IO.Path]::GetFullPath($file.FullName)
            if (-not $full.StartsWith($stagingRoot, [StringComparison]::OrdinalIgnoreCase)) {
                continue
            }
            $rel = $full.Substring($stagingRoot.Length).TrimStart('\')
            $dest = Join-Path $InstallDir $rel
            $destParent = Split-Path -Parent $dest
            if (-not (Test-Path -LiteralPath $destParent)) {
                New-Item -ItemType Directory -Path $destParent -Force | Out-Null
            }
            Copy-Item -LiteralPath $file.FullName -Destination $dest -Force
            $i++
            $bar.Value = [Math]::Min(100, [int](($i * 100) / $total))
            $label.Text = "Installing update... ($i / $total)"
            [System.Windows.Forms.Application]::DoEvents()
        }
        $bar.Value = 100
        $label.Text = "Install complete. Starting Ashen Macros..."
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 400
    } finally {
        Remove-Item -LiteralPath $StagingDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    if (Test-Path -LiteralPath $AppExe) {
        Start-Process -FilePath $AppExe
    }
} finally {
    if ($form -ne $null) {
        try { $form.Close() } catch {}
        try { $form.Dispose() } catch {}
    }
    if ($taken) { [void]$mutex.ReleaseMutex() }
    $mutex.Dispose()
}
"""


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def read_local_version() -> str:
    for path in ("_internal/version", "version"):
        try:
            with open(path, "r", encoding="UTF-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return "0.0.0"


def display_version(plain: str | None = None) -> str:
    """UI version string. Appends ' (dev)' when running from source."""
    value = plain if plain is not None else read_local_version()
    if is_frozen():
        return value
    return f"{value} (dev)"


def prefer_prerelease_enabled() -> bool:
    from core.settings import config_bool

    return config_bool("prefer_prerelease", "false")


def install_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def app_executable() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve()
    return Path(sys.argv[0]).resolve()


def dir_is_writable(path: Path) -> bool:
    """Probe real create/delete rights instead of trusting os.access alone."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".ashen_write_probe_{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="UTF-8")
        probe.unlink()
        return True
    except OSError:
        return False


def zip_asset_name(online_version: str) -> str:
    return f"Ashen-Macros-{online_version}.zip"


def _release_version_name(release: dict) -> str:
    name = str(release.get("name") or "").strip()
    if name:
        return name
    tag = str(release.get("tag_name") or "").strip()
    if tag.lower().startswith("v"):
        return tag[1:]
    return tag


def _fetch_online_release(*, prefer_prerelease: bool) -> dict | None:
    headers = {"Accept": "application/vnd.github+json"}
    if prefer_prerelease:
        response = requests.get(GITHUB_RELEASES_LIST, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        releases = response.json()
        if not isinstance(releases, list) or not releases:
            return None
        prereleases = [r for r in releases if r.get("prerelease")]
        chosen = (prereleases or releases)[0]
        online = _release_version_name(chosen)
        if not online:
            return None
        return {
            "online_version": online,
            "tag_name": str(chosen.get("tag_name") or online),
            "prerelease": bool(chosen.get("prerelease")),
        }

    response = requests.get(GITHUB_RELEASES_LATEST, headers=headers, timeout=15)
    if response.status_code != 200:
        return None
    payload = response.json()
    online = _release_version_name(payload)
    if not online:
        return None
    return {
        "online_version": online,
        "tag_name": str(payload.get("tag_name") or online),
        "prerelease": bool(payload.get("prerelease")),
    }


def check_for_updates(silent: bool = True) -> dict:
    """Returns {kind, online_version?} where kind is one of: noop, outdated, current, dev."""
    try:
        if not is_frozen() and silent:
            return {"kind": "noop"}

        prefer = prefer_prerelease_enabled()
        release = _fetch_online_release(prefer_prerelease=prefer)
        if release is None:
            return {"kind": "noop"}
        local = read_local_version()
        online = release["online_version"]
        if version.parse(local) < version.parse(online):
            return {
                "kind": "outdated",
                "online_version": online,
                "tag_name": release.get("tag_name") or online,
                "prerelease": release.get("prerelease"),
            }
        if version.parse(local) == version.parse(online) and not silent:
            return {"kind": "current", "prerelease": release.get("prerelease")}
        if (version.parse(local) > version.parse(online) or not is_frozen()) and not silent:
            return {"kind": "dev", "prerelease": release.get("prerelease")}
        return {"kind": "noop"}
    except Exception as e:
        logger.warning("Failed to check for updates: %s", e)
        return {"kind": "noop"}


def download_update(
    online_version: str,
    tag_name: str | None = None,
    progress_callback=None,
) -> str:
    """Download the release zip to a user-writable temp path.

    When ``progress_callback`` is provided it is called as
    ``progress_callback(received_bytes, total_bytes)`` during the download.
    ``total_bytes`` may be 0 if Content-Length is missing.

    Returns the absolute path to the downloaded zip.
    """
    if not is_frozen():
        raise RuntimeError("Zip updates are only supported for packaged builds.")

    asset_ref = (tag_name or online_version or "").strip()
    asset = zip_asset_name(online_version)
    logger.info("Downloading update v%s (tag %s, asset %s)", online_version, asset_ref, asset)
    url = f"{GITHUB_DOWNLOAD_BASE}/{asset_ref}/{asset}"

    dest_root = Path(tempfile.gettempdir()) / "AshenMacrosUpdates"
    dest_root.mkdir(parents=True, exist_ok=True)
    path = dest_root / asset
    chunk_size = 256 * 1024

    with requests.get(url, allow_redirects=True, timeout=180, stream=True) as download:
        download.raise_for_status()
        total = int(download.headers.get("Content-Length") or 0)
        received = 0
        with open(path, "wb") as out:
            for chunk in download.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                out.write(chunk)
                received += len(chunk)
                if progress_callback is not None:
                    progress_callback(received, total)

    logger.info("Update downloaded to %s (%s bytes)", path, received)
    return str(path.resolve())


def extract_update(zip_path: str, progress_callback=None) -> str:
    """Extract the release zip to a temp staging directory.

    When ``progress_callback`` is provided it is called as
    ``progress_callback(extracted_bytes, total_uncompressed_bytes)``.
    ``total_uncompressed_bytes`` may be 0 if sizes are unavailable.

    Returns the absolute path to the staging root (helper unwraps a single
    top-level folder). Deletes the zip after a successful extract.
    """
    zip_file = Path(zip_path).resolve()
    if not zip_file.is_file():
        raise FileNotFoundError(zip_file)

    staging = Path(tempfile.gettempdir()) / f"AshenMacrosUpdate_{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_file, "r") as zf:
            members = zf.infolist()
            total = sum(info.file_size for info in members if not info.is_dir())
            extracted = 0
            for info in members:
                # Guard against zip-slip into paths outside staging.
                target = (staging / info.filename).resolve()
                if not str(target).startswith(str(staging.resolve())):
                    raise RuntimeError(f"Unsafe path in update zip: {info.filename}")
                zf.extract(info, staging)
                if not info.is_dir():
                    extracted += info.file_size
                    if progress_callback is not None:
                        progress_callback(extracted, total)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    try:
        zip_file.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete update zip after extract: %s", zip_file)

    logger.info("Update extracted to %s", staging)
    return str(staging.resolve())


def _write_update_helper(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    helper_path = dest_dir / "apply_update.ps1"
    helper_path.write_text(UPDATE_HELPER_PS1, encoding="UTF-8")
    return helper_path


def launch_update_after_exit(staging_dir: str) -> None:
    """Start a breakaway helper that waits for exit, copies staging, relaunches.

    Elevates the helper only when the install directory is not writable
    (e.g. custom install under Program Files).
    """
    staging = Path(staging_dir).resolve()
    if not staging.is_dir():
        raise FileNotFoundError(staging)

    target = install_dir()
    exe = app_executable()
    elevate = not dir_is_writable(target)
    helper = _write_update_helper(staging.parent)

    creationflags = _CREATE_BREAKAWAY_FROM_JOB | _CREATE_NEW_PROCESS_GROUP

    if elevate and os.name == "nt":
        logger.info(
            "Install dir %s is not writable; elevating update helper",
            target,
        )
        ps_args = " ".join(
            [
                "-NoProfile",
                "-ExecutionPolicy Bypass",
                f'-File "{helper}"',
                f"-ProcessId {os.getpid()}",
                f'-StagingDir "{staging}"',
                f'-InstallDir "{target}"',
                f'-AppExe "{exe}"',
            ]
        )
        proc = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f"Start-Process -FilePath powershell.exe -Verb RunAs -ArgumentList '{ps_args}'",
            ],
            creationflags=creationflags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(helper),
                "-ProcessId",
                str(os.getpid()),
                "-StagingDir",
                str(staging),
                "-InstallDir",
                str(target),
                "-AppExe",
                str(exe),
            ],
            creationflags=creationflags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    logger.info(
        "Scheduled staging update after exit: %s -> %s (elevate=%s helper pid %s)",
        staging,
        target,
        elevate,
        proc.pid,
    )
