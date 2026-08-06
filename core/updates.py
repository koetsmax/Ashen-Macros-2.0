"""Release checks and zip-based in-app updates."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import requests
from packaging import version

from core.settings import read_config

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
_CREATE_NO_WINDOW = 0x08000000

UPDATE_HELPER_PS1 = r"""param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$ZipPath,
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [Parameter(Mandatory = $true)][string]$AppExe
)

$ErrorActionPreference = "Stop"

$basenames = @('launcher', 'Ashen Macros')
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 120) {
    try {
        Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
        Start-Sleep -Milliseconds 250
    } catch {
        break
    }
}

foreach ($name in $basenames) {
    Stop-Process -Name $name -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

$staging = Join-Path $env:TEMP ("AshenMacrosUpdate_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $staging | Out-Null
try {
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $staging -Force
    $payload = $staging
    $children = @(Get-ChildItem -LiteralPath $staging)
    if (($children.Count -eq 1) -and $children[0].PSIsContainer) {
        $payload = $children[0].FullName
    }
    Copy-Item -Path (Join-Path $payload "*") -Destination $InstallDir -Recurse -Force
} finally {
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
}

if (Test-Path -LiteralPath $AppExe) {
    Start-Process -FilePath $AppExe
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
    config = read_config()
    return str(config.get("prefer_prerelease", "false")).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


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


def download_update(online_version: str, tag_name: str | None = None) -> str:
    """Download the release zip to a user-writable temp path.

    Returns the absolute path to the downloaded zip.
    """
    if not is_frozen():
        raise RuntimeError("Zip updates are only supported for packaged builds.")

    asset_ref = (tag_name or online_version or "").strip()
    asset = zip_asset_name(online_version)
    logger.info("Downloading update v%s (tag %s, asset %s)", online_version, asset_ref, asset)
    url = f"{GITHUB_DOWNLOAD_BASE}/{asset_ref}/{asset}"
    download = requests.get(url, allow_redirects=True, timeout=180)
    download.raise_for_status()

    dest_root = Path(tempfile.gettempdir()) / "AshenMacrosUpdates"
    dest_root.mkdir(parents=True, exist_ok=True)
    path = dest_root / asset
    path.write_bytes(download.content)
    logger.info("Update downloaded to %s (%s bytes)", path, len(download.content))
    return str(path.resolve())


def _write_update_helper(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    helper_path = dest_dir / "apply_update.ps1"
    helper_path.write_text(UPDATE_HELPER_PS1, encoding="UTF-8")
    return helper_path


def launch_update_after_exit(zip_path: str) -> None:
    """Start a breakaway helper that waits for exit, swaps zip contents, relaunches.

    Elevates the helper only when the install directory is not writable
    (e.g. custom install under Program Files).
    """
    zip_file = Path(zip_path).resolve()
    if not zip_file.is_file():
        raise FileNotFoundError(zip_file)

    target = install_dir()
    exe = app_executable()
    elevate = not dir_is_writable(target)
    helper = _write_update_helper(zip_file.parent)

    creationflags = (
        _CREATE_BREAKAWAY_FROM_JOB
        | _CREATE_NEW_PROCESS_GROUP
        | _CREATE_NO_WINDOW
    )

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
                f'-ZipPath "{zip_file}"',
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
                "-WindowStyle",
                "Hidden",
                "-File",
                str(helper),
                "-ProcessId",
                str(os.getpid()),
                "-ZipPath",
                str(zip_file),
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
        "Scheduled zip update after exit: %s -> %s (elevate=%s helper pid %s)",
        zip_file,
        target,
        elevate,
        proc.pid,
    )


# Back-compat aliases used by older call sites / docs.
def launch_installer_after_exit(installer_path: str) -> None:
    launch_update_after_exit(installer_path)
